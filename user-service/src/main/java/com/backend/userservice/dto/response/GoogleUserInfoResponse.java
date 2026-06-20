package com.backend.userservice.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class GoogleUserInfoResponse {
    private String sub;
    private String email;
    private String name;
    private String picture;
}
