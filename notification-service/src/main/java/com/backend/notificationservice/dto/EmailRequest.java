package com.backend.notificationservice.dto;

import lombok.*;

import java.util.Map;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class EmailRequest {
    private String to;           // Email người nhận
    private String subject;      // Tiêu đề (có thể để null nếu Strategy đã có)
    private String type;         // Loại mail: REGISTRATION_VERIFY, FORGOT_PASSWORD...
    private Map<String, Object> payload; // Chứa code, username, link...
}