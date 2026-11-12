package vn.edu.ptit.weather.exception;

import java.util.Map;
import org.springframework.dao.DataAccessException;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.resource.NoResourceFoundException;
import vn.edu.ptit.weather.dto.ApiResponse;

@RestControllerAdvice
public class GlobalExceptionHandler {
  @ExceptionHandler(ApiException.class)
  ResponseEntity<?> business(ApiException e) {
    return ResponseEntity.status(e.getStatus())
        .body(
            ApiResponse.fail(
                e.getStatus() == 422 ? "validation_error" : "http_" + e.getStatus(),
                e.getMessage(),
                null));
  }

  @ExceptionHandler(MethodArgumentNotValidException.class)
  ResponseEntity<?> validation(MethodArgumentNotValidException e) {
    var issues =
        e.getBindingResult().getFieldErrors().stream()
            .map(
                f ->
                    Map.of(
                        "loc",
                        new String[] {"body", f.getField()},
                        "message",
                        f.getDefaultMessage(),
                        "type",
                        "value_error"))
            .toList();
    return ResponseEntity.unprocessableEntity()
        .body(ApiResponse.fail("validation_error", "Thông tin gửi lên không hợp lệ.", issues));
  }

  @ExceptionHandler({
    HttpMessageNotReadableException.class,
    org.springframework.web.method.annotation.MethodArgumentTypeMismatchException.class,
    org.springframework.web.bind.MissingServletRequestParameterException.class
  })
  ResponseEntity<?> invalid(Exception e) {
    return ResponseEntity.unprocessableEntity()
        .body(ApiResponse.fail("validation_error", "Thông tin gửi lên không hợp lệ.", null));
  }

  @ExceptionHandler(NoResourceFoundException.class)
  ResponseEntity<?> missing(Exception e) {
    return ResponseEntity.status(404).body(ApiResponse.fail("http_404", "Not Found", null));
  }

  @ExceptionHandler({
    DataAccessException.class,
    org.springframework.transaction.TransactionException.class
  })
  ResponseEntity<?> database(Exception e) {
    return ResponseEntity.status(503)
        .body(ApiResponse.fail("http_503", "Không kết nối được cơ sở dữ liệu.", null));
  }

  @ExceptionHandler(org.springframework.web.HttpRequestMethodNotSupportedException.class)
  ResponseEntity<?> method(Exception e) {
    return ResponseEntity.status(405)
        .body(ApiResponse.fail("http_405", "Method Not Allowed", null));
  }

  @ExceptionHandler(org.springframework.web.HttpMediaTypeNotSupportedException.class)
  ResponseEntity<?> media(Exception e) {
    return ResponseEntity.status(415)
        .body(ApiResponse.fail("http_415", "Unsupported Media Type", null));
  }

  @ExceptionHandler(Exception.class)
  ResponseEntity<?> unexpected(Exception e) {
    org.slf4j.LoggerFactory.getLogger(getClass())
        .error("Unhandled request failure: {}", e.getClass().getSimpleName());
    return ResponseEntity.internalServerError()
        .body(ApiResponse.fail("internal_error", "Đã xảy ra lỗi máy chủ.", null));
  }
}
