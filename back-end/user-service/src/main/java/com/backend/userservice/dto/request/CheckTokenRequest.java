package com.backend.userservice.dto.request;

import lombok.*;

@Builder
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class CheckTokenRequest {
    private String token;
}
