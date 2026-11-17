package vn.edu.ptit.weather.service;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.List;
import vn.edu.ptit.weather.dto.ChatDto.Citation;

/**
 * One capability the assistant may invoke. Live weather tools keep numbers out of the model's
 * imagination; the retrieval tool adds passages from the project's own reports.
 */
public interface ChatTool {
  /** Must match the name declared to Gemini. */
  String name();

  /** Gemini functionDeclaration: name, description and an OpenAPI-subset parameter schema. */
  ObjectNode declaration(ObjectMapper json);

  Result execute(JsonNode arguments);

  /** Tool output plus the sources it relied on, if any. */
  record Result(JsonNode payload, List<Citation> citations) {
    public static Result of(JsonNode payload) {
      return new Result(payload, List.of());
    }
  }
}
