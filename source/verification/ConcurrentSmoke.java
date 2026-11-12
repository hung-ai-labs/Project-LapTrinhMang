import java.net.*;
import java.net.http.*;
import java.io.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Local regression smoke: 100 persistent WebSockets, concurrent REST, and one TCP producer. */
public class ConcurrentSmoke {
  public static void main(String[] args) throws Exception {
    String base=args.length>0?args[0]:"http://127.0.0.1:18802";
    if(!Set.of("localhost","127.0.0.1").contains(URI.create(base).getHost())) throw new IllegalArgumentException("Use an isolated localhost server");
    int tcp=args.length>1?Integer.parseInt(args[1]):19902,users=100,loops=5;
    var client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
    var failures=new AtomicInteger();var closing=new AtomicBoolean();var latencies=Collections.synchronizedList(new ArrayList<Long>());
    var updates=new ArrayList<AtomicInteger>();var sockets=new ArrayList<CompletableFuture<WebSocket>>();
    for(int i=0;i<users;i++) {
      var count=new AtomicInteger();updates.add(count);
      sockets.add(client.newWebSocketBuilder().buildAsync(URI.create(base.replace("http://","ws://")+"/api/v1/ws/wards/00004/weather"),new WebSocket.Listener() {
        StringBuilder frame=new StringBuilder();
        public void onOpen(WebSocket socket) { socket.request(1); }
        public CompletionStage<?> onText(WebSocket socket,CharSequence chunk,boolean last) {
          frame.append(chunk);
          if(last) { String message=frame.toString();frame.setLength(0);
            if(message.contains("\"type\":\"weather.update\"")) { if(message.contains("\"ward_id\":\"00004\"") && message.contains("\"source\":\"simulator\"")) count.incrementAndGet();else failures.incrementAndGet(); }
            else if(!message.contains("\"type\":\"heartbeat\"")) failures.incrementAndGet();
          }
          socket.request(1);return null;
        }
        public CompletionStage<?> onClose(WebSocket socket,int status,String reason) { if(!closing.get()) failures.incrementAndGet();return null; }
        public void onError(WebSocket socket,Throwable error) { if(!closing.get()) failures.incrementAndGet(); }
      }));
    }
    CompletableFuture.allOf(sockets.toArray(CompletableFuture[]::new)).get(20,TimeUnit.SECONDS);
    var pool=Executors.newFixedThreadPool(users+1);long start=System.nanoTime();
    try {
      var producer=pool.submit(() -> {
        try(Socket socket=new Socket("127.0.0.1",tcp)) {
          socket.setSoTimeout(10000);var reader=new BufferedReader(new InputStreamReader(socket.getInputStream()));
          for(int i=0;i<12;i++) {
            String frame="{\"event_id\":\""+UUID.randomUUID()+"\",\"ward_id\":\"00004\",\"temperature\":36,\"humidity\":80,\"wind_speed\":55,\"rainfall\":25,\"source\":\"simulator\",\"observed_at\":\""+Instant.now()+"\"}\n";
            socket.getOutputStream().write(frame.getBytes(java.nio.charset.StandardCharsets.UTF_8));socket.getOutputStream().flush();String ack=reader.readLine();if(ack==null || !ack.contains("\"status\":\"accepted\"")) failures.incrementAndGet();Thread.sleep(250);
          }
        } catch(Exception e) { failures.incrementAndGet();throw new RuntimeException(e); }
      });
      var requests=new ArrayList<Future<?>>();String[] paths={"/api/v1/provinces?page_size=100","/api/v1/wards?province_id=01&page_size=100","/api/v1/wards/00004/weather/current","/api/v1/wards/00004/weather/history?page_size=60"};
      for(int user=0;user<users;user++) requests.add(pool.submit(() -> {
        for(int loop=0;loop<loops;loop++) for(String path:paths) {
          long began=System.nanoTime();
          try { var response=client.send(HttpRequest.newBuilder(URI.create(base+path)).timeout(Duration.ofSeconds(20)).GET().build(),HttpResponse.BodyHandlers.ofString());if(response.statusCode()!=200 || !response.body().contains("\"success\":true")) failures.incrementAndGet(); }
          catch(Exception e) { failures.incrementAndGet(); }
          latencies.add(TimeUnit.NANOSECONDS.toMillis(System.nanoTime()-began));
        }
      }));
      for(var request:requests) request.get(60,TimeUnit.SECONDS);producer.get(20,TimeUnit.SECONDS);
      long recipients=updates.stream().filter(n -> n.get()>0).count();latencies.sort(Long::compare);
      System.out.printf(Locale.ROOT,"{\"users\":%d,\"http_samples\":%d,\"errors\":%d,\"ws_receiving_updates\":%d,\"http_p95_ms\":%d,\"duration_seconds\":%.2f}%n",users,latencies.size(),failures.get(),recipients,latencies.get((int)Math.ceil(latencies.size()*0.95)-1),(System.nanoTime()-start)/1e9);
      if(failures.get()!=0 || recipients!=users) throw new AssertionError("Concurrent smoke failed");
    } finally { closing.set(true);for(var socket:sockets) socket.join().sendClose(WebSocket.NORMAL_CLOSURE,"done");pool.shutdownNow(); }
  }
}
