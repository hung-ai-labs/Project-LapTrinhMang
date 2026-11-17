package vn.edu.ptit.weather.tool;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

/** Builds the OpenAPI-subset schemas Gemini expects inside a functionDeclaration. */
final class Schemas {
  private Schemas() {}

  static ObjectNode declaration(
      ObjectMapper json, String name, String description, ObjectNode parameters) {
    ObjectNode declaration = json.createObjectNode();
    declaration.put("name", name);
    declaration.put("description", description);
    declaration.set("parameters", parameters);
    return declaration;
  }

  /** An object schema; {@code required} lists the properties Gemini must always supply. */
  static ObjectNode object(ObjectMapper json, ObjectNode properties, String... required) {
    ObjectNode schema = json.createObjectNode();
    schema.put("type", "OBJECT");
    schema.set("properties", properties);
    var names = json.createArrayNode();
    for (String field : required) names.add(field);
    if (!names.isEmpty()) schema.set("required", names);
    return schema;
  }

  static ObjectNode string(ObjectMapper json, String description) {
    return json.createObjectNode().put("type", "STRING").put("description", description);
  }

  static ObjectNode integer(ObjectMapper json, String description) {
    return json.createObjectNode().put("type", "INTEGER").put("description", description);
  }

  /** Gemini may omit optional arguments entirely, so every read must tolerate a missing node. */
  static String text(com.fasterxml.jackson.databind.JsonNode arguments, String field) {
    var value = arguments.path(field);
    return value.isTextual() ? value.asText().strip() : "";
  }

  static int number(com.fasterxml.jackson.databind.JsonNode arguments, String field, int fallback) {
    var value = arguments.path(field);
    return value.isInt() || value.isLong() ? value.asInt() : fallback;
  }
}
