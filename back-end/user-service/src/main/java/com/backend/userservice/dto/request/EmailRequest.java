package com.backend.userservice.dto.request;

import lombok.*;

import java.util.Map;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class EmailRequest {
    private String to;
    private String type;
    private Map<String, Object> payload;
}