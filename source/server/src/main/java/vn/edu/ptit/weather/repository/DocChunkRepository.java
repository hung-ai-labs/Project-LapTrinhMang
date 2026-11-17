package vn.edu.ptit.weather.repository;

import java.util.*;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

/**
 * Plain JDBC on purpose: pgvector's {@code vector} type has no Hibernate mapping, and keeping it
 * out of JPA also keeps the H2 test schema buildable.
 */
@Repository
@RequiredArgsConstructor
public class DocChunkRepository {
  public record Chunk(
      String id,
      String sourcePath,
      String heading,
      int chunkIndex,
      String content,
      String contentHash) {}

  public record Match(String sourcePath, String heading, String content, double score) {}

  private final JdbcTemplate db;

  public boolean ready() {
    Integer tables =
        db.queryForObject(
            "SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tablename='doc_chunks'",
            Integer.class);
    return tables != null && tables > 0;
  }

  public long count() {
    Long rows = db.queryForObject("SELECT count(*) FROM doc_chunks", Long.class);
    return rows == null ? 0 : rows;
  }

  public Set<String> hashesFor(String sourcePath) {
    return new HashSet<>(
        db.queryForList(
            "SELECT content_hash FROM doc_chunks WHERE source_path = ?",
            String.class,
            sourcePath));
  }

  public void insert(Chunk chunk, float[] embedding) {
    db.update(
        "INSERT INTO doc_chunks(id,source_path,heading,chunk_index,content,content_hash,embedding)"
            + " VALUES (?,?,?,?,?,?,?::vector) ON CONFLICT (content_hash) DO NOTHING",
        chunk.id(),
        chunk.sourcePath(),
        chunk.heading(),
        chunk.chunkIndex(),
        chunk.content(),
        chunk.contentHash(),
        literal(embedding));
  }

  /** Drops chunks of a file that no longer exist after a re-index. */
  public int deleteMissing(String sourcePath, Collection<String> keepHashes) {
    if (keepHashes.isEmpty())
      return db.update("DELETE FROM doc_chunks WHERE source_path = ?", sourcePath);
    String placeholders = String.join(",", Collections.nCopies(keepHashes.size(), "?"));
    var parameters = new ArrayList<Object>();
    parameters.add(sourcePath);
    parameters.addAll(keepHashes);
    return db.update(
        "DELETE FROM doc_chunks WHERE source_path = ? AND content_hash NOT IN (" + placeholders + ")",
        parameters.toArray());
  }

  public int deleteOtherSources(Collection<String> keepPaths) {
    if (keepPaths.isEmpty()) return db.update("DELETE FROM doc_chunks");
    String placeholders = String.join(",", Collections.nCopies(keepPaths.size(), "?"));
    return db.update(
        "DELETE FROM doc_chunks WHERE source_path NOT IN (" + placeholders + ")",
        keepPaths.toArray());
  }

  /** Cosine similarity: pgvector's {@code <=>} returns distance, so similarity is 1 - distance. */
  public List<Match> search(float[] query, int topK) {
    String vector = literal(query);
    return db.query(
        "SELECT source_path, heading, content, 1 - (embedding <=> ?::vector) AS score"
            + " FROM doc_chunks ORDER BY embedding <=> ?::vector LIMIT ?",
        (rs, row) ->
            new Match(
                rs.getString("source_path"),
                rs.getString("heading"),
                rs.getString("content"),
                rs.getDouble("score")),
        vector,
        vector,
        topK);
  }

  private static String literal(float[] values) {
    var text = new StringBuilder(values.length * 12).append('[');
    for (int i = 0; i < values.length; i++) {
      if (i > 0) text.append(',');
      text.append(values[i]);
    }
    return text.append(']').toString();
  }
}
