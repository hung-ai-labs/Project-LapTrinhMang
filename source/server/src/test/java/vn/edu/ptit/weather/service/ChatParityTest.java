package vn.edu.ptit.weather.service;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.util.List;
import org.junit.jupiter.api.Test;
import vn.edu.ptit.weather.entity.*;
import vn.edu.ptit.weather.exception.ApiException;
import vn.edu.ptit.weather.tool.FindWardTool;

/** Covers the chatbot pieces that must behave correctly without calling Gemini. */
class ChatParityTest {
  private final ObjectMapper json = new ObjectMapper();

  // --- Markdown chunking ---

  @Test
  void splitsSectionsAtHeadings() {
    var passages =
        MarkdownChunker.split(
            """
            # Tiêu đề
            Đoạn mở đầu đủ dài để giữ lại trong chỉ mục tìm kiếm của dự án này.

            ## Mục hai
            Nội dung của mục hai cũng đủ dài để không bị loại bỏ khỏi chỉ mục.
            """);
    assertThat(passages).hasSize(2);
    assertThat(passages.get(0).heading()).isEqualTo("Tiêu đề");
    assertThat(passages.get(1).heading()).isEqualTo("Mục hai");
    assertThat(passages.get(1).text()).contains("mục hai");
  }

  @Test
  void treatsHashInsideCodeFenceAsContentNotHeading() {
    var passages =
        MarkdownChunker.split(
            """
            # Cách chạy
            Chạy lệnh sau trong thư mục server để khởi tạo lại chỉ mục tài liệu:

            ```sh
            # đây là comment shell, không phải heading
            mvn spring-boot:run
            ```
            """);
    assertThat(passages).hasSize(1);
    assertThat(passages.get(0).heading()).isEqualTo("Cách chạy");
    assertThat(passages.get(0).text()).contains("comment shell");
  }

  @Test
  void windowsLongSectionsWithOverlap() {
    String body = ("từ ".repeat(1000)).strip();
    var passages = MarkdownChunker.split("# Dài\n" + body);
    assertThat(passages.size()).isGreaterThan(1);
    // 400-word windows advancing 350 words must cover every word of the section.
    assertThat(passages.get(0).text().split("\\s+")).hasSize(400);
  }

  @Test
  void embeddableKeepsSourceAndHeadingWithTheBody() {
    String text =
        MarkdownChunker.embeddable(
            "reports/Benchmark.md", new MarkdownChunker.Passage("Kết quả", "AP trung bình 0,154"));
    assertThat(text).contains("reports/Benchmark.md").contains("Kết quả").contains("0,154");
  }

  // --- Rate limiting ---

  @Test
  void allowsUpToTheLimitThenRejects() {
    var limiter = new ChatRateLimiter(3);
    for (int i = 0; i < 3; i++) limiter.check("user-1");
    assertThatThrownBy(() -> limiter.check("user-1"))
        .isInstanceOf(ApiException.class)
        .hasMessageContaining("quá 3 câu hỏi");
  }

  @Test
  void countsEachUserSeparately() {
    var limiter = new ChatRateLimiter(1);
    limiter.check("user-1");
    assertThatCode(() -> limiter.check("user-2")).doesNotThrowAnyException();
  }

  @Test
  void zeroLimitDisablesThrottling() {
    var limiter = new ChatRateLimiter(0);
    for (int i = 0; i < 50; i++) limiter.check("user-1");
  }

  // --- Ward lookup used by the weather tools ---

  private Ward ward(String id, String name, String provinceId) {
    Ward ward = new Ward();
    ward.setId(id);
    ward.setName(name);
    ward.setProvinceId(provinceId);
    ward.setLatitude(new BigDecimal("21.00000"));
    ward.setLongitude(new BigDecimal("105.00000"));
    return ward;
  }

  private FindWardTool findWardTool() {
    Province province = new Province();
    province.setId("01");
    province.setName("Hà Nội");
    var geography = mock(GeographyService.class);
    when(geography.provinces())
        .thenReturn(new GeographyService.Catalog<>(List.of(province), java.time.Instant.now(), false));
    when(geography.wards(null))
        .thenReturn(
            new GeographyService.Catalog<>(
                List.of(ward("00004", "Phường Láng", "01"), ward("00007", "Phường Ngọc Hà", "01")),
                java.time.Instant.now(),
                false));
    return new FindWardTool(geography, json);
  }

  @Test
  void findsWardIgnoringDiacritics() {
    var result = findWardTool().execute(json.createObjectNode().put("query", "phuong lang"));
    assertThat(result.payload().path("count").asInt()).isEqualTo(1);
    assertThat(result.payload().path("wards").path(0).path("ward_id").asText()).isEqualTo("00004");
    assertThat(result.payload().path("wards").path(0).path("province_name").asText())
        .isEqualTo("Hà Nội");
  }

  @Test
  void findsEveryWardOfAProvinceByProvinceName() {
    var result = findWardTool().execute(json.createObjectNode().put("query", "ha noi"));
    assertThat(result.payload().path("count").asInt()).isEqualTo(2);
  }

  @Test
  void reportsNoMatchInsteadOfGuessing() {
    var result = findWardTool().execute(json.createObjectNode().put("query", "không có thật"));
    assertThat(result.payload().path("count").asInt()).isZero();
    assertThat(result.payload().path("hint").asText()).contains("Không tìm thấy");
  }

  @Test
  void rejectsMissingQueryWithoutThrowing() {
    var result = findWardTool().execute(json.createObjectNode());
    assertThat(result.payload().path("error").asText()).isNotBlank();
  }

  // --- Weather advisory ---

  @Test
  void advisoryStaysSilentWhenTheAssistantIsNotConfigured() {
    var gemini = mock(GeminiClient.class);
    when(gemini.configured()).thenReturn(false);
    var geography = mock(GeographyService.class);
    when(geography.ward("00004")).thenReturn(ward("00004", "Phường Láng", "01"));

    var advice = new AdviceService(mock(ChatService.class), gemini, geography);
    var response = advice.advice("00004");

    assertThat(response.available()).isFalse();
    assertThat(response.reason()).contains("GEMINI_API_KEY");
    assertThat(response.advice()).isNull();
  }

  @Test
  void advisoryDegradesInsteadOfPropagatingUpstreamFailure() {
    var gemini = mock(GeminiClient.class);
    when(gemini.configured()).thenReturn(true);
    var geography = mock(GeographyService.class);
    when(geography.ward("00004")).thenReturn(ward("00004", "Phường Láng", "01"));
    var chat = mock(ChatService.class);
    when(chat.singleTurn(anyString())).thenReturn(json.createArrayNode());
    when(chat.complete(any(), anyString(), any()))
        .thenThrow(new ApiException(503, "Gemini đang quá tải, vui lòng thử lại sau ít phút."));

    var response = new AdviceService(chat, gemini, geography).advice("00004");

    assertThat(response.available()).isFalse();
    assertThat(response.reason()).contains("quá tải");
  }

  @Test
  void advisoryReusesOneGenerationPerWard() {
    var gemini = mock(GeminiClient.class);
    when(gemini.configured()).thenReturn(true);
    var geography = mock(GeographyService.class);
    when(geography.ward("00004")).thenReturn(ward("00004", "Phường Láng", "01"));
    var chat = mock(ChatService.class);
    when(chat.singleTurn(anyString())).thenReturn(json.createArrayNode());
    when(chat.complete(any(), anyString(), any()))
        .thenReturn(new ChatService.Completion("Trời lạnh, nhớ mặc áo ấm.", List.of()));

    var advice = new AdviceService(chat, gemini, geography);
    var first = advice.advice("00004");
    var second = advice.advice("00004");

    assertThat(first.available()).isTrue();
    assertThat(second.advice()).isEqualTo(first.advice());
    // Cached: the second reader must not cost another Gemini call.
    verify(chat, times(1)).complete(any(), anyString(), any());
  }

  @Test
  void declaresSchemaGeminiCanParse() {
    var declaration = findWardTool().declaration(json);
    assertThat(declaration.path("name").asText()).isEqualTo("find_ward");
    assertThat(declaration.path("description").asText()).isNotBlank();
    assertThat(declaration.path("parameters").path("type").asText()).isEqualTo("OBJECT");
    assertThat(declaration.path("parameters").path("properties").path("query").path("type").asText())
        .isEqualTo("STRING");
    assertThat(declaration.path("parameters").path("required").get(0).asText()).isEqualTo("query");
  }
}
