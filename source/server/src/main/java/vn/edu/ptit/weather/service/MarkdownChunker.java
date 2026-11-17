package vn.edu.ptit.weather.service;

import java.util.*;

/**
 * Splits a markdown report into retrievable passages. Sections are cut at headings because the
 * project's reports are written that way; over-long sections are then windowed with an overlap so
 * a sentence spanning the boundary still lands whole in one chunk.
 */
public final class MarkdownChunker {
  private static final int TARGET_WORDS = 400;
  private static final int OVERLAP_WORDS = 50;
  private static final int MIN_WORDS = 15;

  private MarkdownChunker() {}

  public record Passage(String heading, String text) {}

  public static List<Passage> split(String markdown) {
    var passages = new ArrayList<Passage>();
    String heading = "";
    var body = new StringBuilder();
    boolean insideFence = false;

    for (String line : markdown.replace("\r\n", "\n").split("\n", -1)) {
      if (line.startsWith("```")) insideFence = !insideFence;
      // A '#' inside a fenced block is code or a shell comment, not a section break.
      if (!insideFence && line.startsWith("#")) {
        flush(passages, heading, body.toString());
        body.setLength(0);
        heading = line.replaceAll("^#+\\s*", "").strip();
        continue;
      }
      body.append(line).append('\n');
    }
    flush(passages, heading, body.toString());
    return passages;
  }

  private static void flush(List<Passage> passages, String heading, String body) {
    String text = body.strip();
    if (text.isEmpty()) return;
    String[] words = text.split("\\s+");
    if (words.length <= TARGET_WORDS) {
      add(passages, heading, text, words.length);
      return;
    }
    int step = TARGET_WORDS - OVERLAP_WORDS;
    for (int start = 0; start < words.length; start += step) {
      int end = Math.min(start + TARGET_WORDS, words.length);
      add(
          passages,
          heading,
          String.join(" ", Arrays.copyOfRange(words, start, end)),
          end - start);
      if (end == words.length) break;
    }
  }

  private static void add(List<Passage> passages, String heading, String text, int words) {
    // Headings alone carry no answer; drop slivers rather than pollute the index.
    if (words < MIN_WORDS && heading.isBlank()) return;
    passages.add(new Passage(heading, text));
  }

  /** The heading is embedded with the body so a passage keeps its topic when retrieved alone. */
  public static String embeddable(String sourcePath, Passage passage) {
    var text = new StringBuilder();
    text.append("Nguồn: ").append(sourcePath).append('\n');
    if (!passage.heading().isBlank()) text.append("Mục: ").append(passage.heading()).append('\n');
    return text.append(passage.text()).toString();
  }
}
