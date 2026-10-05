package com.backend.documentservice.controller;

import com.backend.documentservice.dto.response.ApiResponse;
import com.backend.documentservice.service.LectureScriptService;
import com.backend.documentservice.service.ScriptSetService;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.UUID;

/** Lecture script for an uploaded deck: write, rewrite on request, export to Excel, keep as sets. */
@RestController
@RequestMapping("/lecture-script")
@RequiredArgsConstructor
public class LectureScriptController {

    private static final String XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

    private final LectureScriptService lectureScriptService;
    private final ScriptSetService scriptSetService;

    private UUID currentUserId() {
        return UUID.fromString(SecurityContextHolder.getContext().getAuthentication().getName());
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ApiResponse<JsonNode> start(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "prompt", required = false) String prompt,
            @RequestParam(value = "firstVideo", required = false, defaultValue = "false") boolean firstVideo) {
        return ApiResponse.<JsonNode>builder().data(lectureScriptService.start(file, prompt, firstVideo)).build();
    }

    @PostMapping("/revise")
    public ApiResponse<JsonNode> revise(@RequestBody JsonNode request) {
        return ApiResponse.<JsonNode>builder().data(lectureScriptService.revise(request)).build();
    }

    @GetMapping("/status/{taskId}")
    public ApiResponse<JsonNode> status(@PathVariable String taskId) {
        return ApiResponse.<JsonNode>builder().data(lectureScriptService.status(taskId)).build();
    }

    @PostMapping("/export")
    public ResponseEntity<byte[]> export(@RequestBody JsonNode request) {
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"kich-ban-dung.xlsx\"")
                .contentType(MediaType.parseMediaType(XLSX))
                .body(lectureScriptService.export(request));
    }

    @GetMapping("/sets")
    public ApiResponse<JsonNode> listSets() {
        return ApiResponse.<JsonNode>builder().data(scriptSetService.list(currentUserId())).build();
    }

    @PostMapping("/sets")
    public ApiResponse<JsonNode> createSet(@RequestBody JsonNode request) {
        return ApiResponse.<JsonNode>builder().data(scriptSetService.create(currentUserId(), request)).build();
    }

    @GetMapping("/sets/{id}")
    public ApiResponse<JsonNode> getSet(@PathVariable UUID id) {
        return ApiResponse.<JsonNode>builder().data(scriptSetService.get(id, currentUserId())).build();
    }

    @PutMapping("/sets/{id}")
    public ApiResponse<JsonNode> updateSet(@PathVariable UUID id, @RequestBody JsonNode request) {
        return ApiResponse.<JsonNode>builder().data(scriptSetService.update(id, currentUserId(), request)).build();
    }

    @DeleteMapping("/sets/{id}")
    public ApiResponse<Void> deleteSet(@PathVariable UUID id) {
        scriptSetService.delete(id, currentUserId());
        return ApiResponse.<Void>builder().message("Đã xoá bộ kịch bản").build();
    }
}
