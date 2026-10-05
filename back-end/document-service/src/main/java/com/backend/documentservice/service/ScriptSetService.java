package com.backend.documentservice.service;

import com.backend.documentservice.entity.ScriptSet;
import com.backend.documentservice.exception.AppException;
import com.backend.documentservice.exception.ErrorCode;
import com.backend.documentservice.repository.ScriptSetRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.UUID;

/** Saved sets of lecture scripts: listed, reopened, edited and exported again without the AI. */
@Service
@RequiredArgsConstructor
public class ScriptSetService {

    private static final int WORDS_PER_MINUTE = 140;
    private static final int MAX_ITEMS = 20;
    private static final int MAX_CONTENT_CHARS = 8_000_000;
    private static final int MAX_SETS_PER_USER = 500;

    private final ScriptSetRepository repository;
    private final ObjectMapper objectMapper;

    @Transactional(readOnly = true)
    public JsonNode list(UUID userId) {
        ArrayNode list = objectMapper.createArrayNode();
        repository.findSummariesByUserId(userId).forEach(row -> {
            ObjectNode node = list.addObject();
            node.put("id", row.getId().toString());
            node.put("name", row.getName());
            node.put("itemCount", row.getItemCount() == null ? 0 : row.getItemCount());
            node.put("totalWords", row.getTotalWords() == null ? 0 : row.getTotalWords());
            node.put("totalMinutes", row.getTotalMinutes() == null ? 0 : row.getTotalMinutes());
            node.put("createdAt", String.valueOf(row.getCreatedAt()));
            node.put("updatedAt", String.valueOf(row.getUpdatedAt()));
        });
        return list;
    }

    @Transactional(readOnly = true)
    public JsonNode get(UUID id, UUID userId) {
        return detail(owned(id, userId));
    }

    @Transactional
    public JsonNode create(UUID userId, JsonNode request) {
        if (repository.countByUserId(userId) >= MAX_SETS_PER_USER) {
            throw new AppException(ErrorCode.INVALID_KEY,
                    "Bạn đã lưu tối đa " + MAX_SETS_PER_USER + " bộ kịch bản. Hãy xoá bớt bộ cũ.");
        }
        ScriptSet set = new ScriptSet();
        set.setUserId(userId);
        set.setIsActive(true);
        apply(set, request);
        return summary(repository.save(set));
    }

    @Transactional
    public JsonNode update(UUID id, UUID userId, JsonNode request) {
        ScriptSet set = owned(id, userId);
        apply(set, request);
        set.setUpdatedAt(Instant.now());
        return summary(repository.save(set));
    }

    @Transactional
    public void delete(UUID id, UUID userId) {
        repository.delete(owned(id, userId));
    }

    private ScriptSet owned(UUID id, UUID userId) {
        return repository.findByIdAndUserId(id, userId)
                .orElseThrow(() -> new AppException(ErrorCode.DOCUMENT_NOT_FOUND, "Không tìm thấy bộ kịch bản"));
    }

    private void apply(ScriptSet set, JsonNode request) {
        JsonNode items = request == null ? null : request.get("items");
        if (items == null || !items.isArray() || items.isEmpty()) {
            throw new AppException(ErrorCode.INVALID_KEY, "Bộ kịch bản chưa có kịch bản nào");
        }
        if (items.size() > MAX_ITEMS) {
            throw new AppException(ErrorCode.INVALID_KEY, "Một bộ tối đa " + MAX_ITEMS + " kịch bản");
        }
        String content = items.toString();
        if (content.length() > MAX_CONTENT_CHARS) {
            throw new AppException(ErrorCode.INVALID_KEY, "Bộ kịch bản quá lớn để lưu");
        }
        String name = request.path("name").asText("").trim();
        if (name.isEmpty()) {
            name = items.get(0).path("title").asText("").trim();
        }
        if (name.isEmpty()) {
            name = "Bộ kịch bản";
        }
        int words = 0;
        int minutes = 0;
        for (JsonNode item : items) {
            int itemWords = 0;
            for (JsonNode row : item.path("rows")) {
                String script = row.path("script").asText("").trim();
                if (!script.isEmpty()) {
                    itemWords += script.split("\\s+").length;
                }
            }
            words += itemWords;
            minutes += itemWords == 0 ? 0 : Math.max(1, Math.round(itemWords / (float) WORDS_PER_MINUTE));
        }
        String prompt = request.path("prompt").asText("");
        set.setName(name.length() > 200 ? name.substring(0, 200) : name);
        set.setPrompt(prompt.length() > 1500 ? prompt.substring(0, 1500) : prompt);
        set.setItemCount(items.size());
        set.setTotalWords(words);
        set.setTotalMinutes(minutes);
        set.setContent(content);
    }

    /** What a save answers with: the list row, not the scripts the caller just sent. */
    private ObjectNode summary(ScriptSet set) {
        ObjectNode node = objectMapper.createObjectNode();
        node.put("id", set.getId().toString());
        node.put("name", set.getName());
        node.put("prompt", set.getPrompt() == null ? "" : set.getPrompt());
        node.put("itemCount", set.getItemCount() == null ? 0 : set.getItemCount());
        node.put("totalWords", set.getTotalWords() == null ? 0 : set.getTotalWords());
        node.put("totalMinutes", set.getTotalMinutes() == null ? 0 : set.getTotalMinutes());
        node.put("updatedAt", String.valueOf(set.getUpdatedAt()));
        return node;
    }

    private JsonNode detail(ScriptSet set) {
        ObjectNode node = summary(set);
        try {
            node.set("items", objectMapper.readTree(set.getContent() == null ? "[]" : set.getContent()));
        } catch (Exception exception) {
            node.set("items", objectMapper.createArrayNode());
        }
        return node;
    }
}
