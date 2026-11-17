package vn.edu.ptit.weather.tool;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.ArrayList;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import vn.edu.ptit.weather.dto.ChatDto.Citation;
import vn.edu.ptit.weather.service.ChatTool;
import vn.edu.ptit.weather.service.DocumentIndexService;

/**
 * Retrieval over the project's own research reports. Passages are returned with their file and
 * heading so the answer can cite them; an empty result is reported honestly rather than guessed at.
 */
@Component
public class SearchDocumentsTool implements ChatTool {
  private final DocumentIndexService documents;
  private final ObjectMapper json;
  private final int topK;
  private final double minScore;

  public SearchDocumentsTool(
      DocumentIndexService documents,
      ObjectMapper json,
      @Value("${weather.rag-top-k}") int topK,
      @Value("${weather.rag-min-score}") double minScore) {
    this.documents = documents;
    this.json = json;
    this.topK = topK;
    this.minScore = minScore;
  }

  @Override
  public String name() {
    return "search_documents";
  }

  @Override
  public ObjectNode declaration(ObjectMapper mapper) {
    ObjectNode properties = mapper.createObjectNode();
    properties.set(
        "question",
        Schemas.string(mapper, "Câu hỏi cần tra cứu trong tài liệu nghiên cứu của dự án."));
    return Schemas.declaration(
        mapper,
        name(),
        "Tra cứu báo cáo nghiên cứu của dự án: mô hình dự báo ngập Hà Nội, benchmark, ablation, "
            + "dữ liệu và kiến trúc hệ thống. Dùng khi người dùng hỏi về nghiên cứu hoặc tài liệu, "
            + "không dùng cho số liệu thời tiết hiện tại.",
        Schemas.object(mapper, properties, "question"));
  }

  @Override
  public Result execute(JsonNode arguments) {
    String question = Schemas.text(arguments, "question");
    if (question.isBlank())
      return Result.of(json.createObjectNode().put("error", "Thiếu nội dung cần tra cứu."));

    var matches = documents.search(question, topK, minScore);
    ObjectNode payload = json.createObjectNode();
    if (matches.isEmpty()) {
      payload.put("found", false);
      payload.put(
          "note", "Không có đoạn tài liệu nào đủ liên quan. Hãy nói rõ tài liệu dự án không đề cập.");
      return Result.of(payload);
    }

    var citations = new ArrayList<Citation>();
    var passages = json.createArrayNode();
    for (var match : matches) {
      ObjectNode row = json.createObjectNode();
      row.put("source_path", match.sourcePath());
      row.put("heading", match.heading() == null ? "" : match.heading());
      row.put("score", Math.round(match.score() * 1000) / 1000.0);
      row.put("content", match.content());
      passages.add(row);
      citations.add(
          new Citation(
              match.sourcePath(),
              match.heading() == null ? "" : match.heading(),
              Math.round(match.score() * 1000) / 1000.0));
    }
    payload.put("found", true);
    payload.set("passages", passages);
    return new Result(payload, citations);
  }
}
