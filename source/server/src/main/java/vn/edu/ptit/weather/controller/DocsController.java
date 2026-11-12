package vn.edu.ptit.weather.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ResponseBody;

@Controller
public class DocsController {
  @GetMapping("/openapi.json")
  public String schemaAlias() {
    return "forward:/v3/api-docs";
  }

  @GetMapping(value = "/redoc", produces = "text/html")
  @ResponseBody
  public String redoc() {
    return """
      <!doctype html><html><head><meta charset="utf-8"><title>Weather Stream API</title></head>
      <body><redoc spec-url="/openapi.json"></redoc><script src="https://cdn.jsdelivr.net/npm/redoc@2/bundles/redoc.standalone.js"></script></body></html>
      """;
  }
}
