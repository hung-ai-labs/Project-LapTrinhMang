package vn.edu.ptit.weather.service;

import java.util.*;
import java.util.concurrent.*;
import java.util.function.Supplier;
import vn.edu.ptit.weather.exception.ApiException;

/** Share only work in flight; completed calls never become a forecast cache. */
final class SharedRequests implements AutoCloseable {
  private final Map<String, CompletableFuture<Object>> pending = new HashMap<>();
  private final ExecutorService workers;
  private final int capacity;

  SharedRequests(int concurrency, int capacity) {
    this.capacity = capacity;
    this.workers =
        Executors.newFixedThreadPool(
            concurrency,
            task -> {
              Thread thread = new Thread(task, "weather-provider-worker");
              thread.setDaemon(true);
              return thread;
            });
  }

  Object get(String key, Supplier<Object> load) {
    CompletableFuture<Object> future;
    synchronized (pending) {
      if (workers.isShutdown()) throw new ApiException(503, "Server đang dừng.");
      future = pending.get(key);
      if (future != null && future.isDone()) {
        pending.remove(key, future);
        future = null;
      }
      if (future == null) {
        if (pending.size() >= capacity) throw new ApiException(503, "Hàng đợi dự báo đang đầy.");
        future = new CompletableFuture<>();
        pending.put(key, future);
        final var shared = future;
        workers.execute(
            () -> {
              try {
                shared.complete(load.get());
              } catch (Throwable error) {
                shared.completeExceptionally(error);
              } finally {
                synchronized (pending) {
                  pending.remove(key, shared);
                }
              }
            });
      }
    }
    try {
      return future.get(30, TimeUnit.SECONDS);
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw new ApiException(503, "Đã hủy chờ dự báo.");
    } catch (TimeoutException e) {
      throw new ApiException(503, "Dự báo quá thời gian chờ.");
    } catch (ExecutionException e) {
      if (e.getCause() instanceof RuntimeException error) throw error;
      throw new ApiException(503, "Không lấy được dự báo.");
    }
  }

  @Override
  public void close() {
    workers.shutdownNow();
    synchronized (pending) {
      pending
          .values()
          .forEach(f -> f.completeExceptionally(new ApiException(503, "Server đang dừng.")));
      pending.clear();
    }
  }
}
