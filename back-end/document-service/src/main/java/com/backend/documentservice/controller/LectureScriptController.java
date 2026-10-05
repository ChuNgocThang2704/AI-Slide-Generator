package com.backend.documentservice.controller;

import com.backend.documentservice.dto.response.ApiResponse;
import com.backend.documentservice.service.LectureScriptService;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

/** Lecture script for an uploaded deck: write, rewrite on request, export to Excel. */
@RestController
@RequestMapping("/lecture-script")
@RequiredArgsConstructor
public class LectureScriptController {

    private static final String XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

    private final LectureScriptService lectureScriptService;

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ApiResponse<JsonNode> start(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "prompt", required = false) String prompt) {
        return ApiResponse.<JsonNode>builder().data(lectureScriptService.start(file, prompt)).build();
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
}
