package vn.edu.ptit.weather.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

/**
 * Hands client-side routes back to the React bundle. The paths are listed one by one on purpose: a
 * catch-all would also swallow /api/**, /docs and the WebSocket upgrade, turning real 404s into a
 * page of HTML. Add a line here whenever the client gains a route.
 *
 * <p>"/" needs no entry — Spring Boot serves index.html from the static locations as the welcome
 * page.
 */
@Controller
public class SpaController {
  @GetMapping({"/login", "/register", "/alerts", "/forecast", "/chat"})
  public String clientRoute() {
    return "forward:/index.html";
  }
}
