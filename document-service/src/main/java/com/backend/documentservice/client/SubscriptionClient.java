package com.backend.documentservice.client;

import com.backend.documentservice.configuration.FeignClientConfig;
import com.backend.documentservice.dto.request.InternalQuotaRequest;
import com.backend.documentservice.dto.response.ApiResponse;
import com.backend.documentservice.dto.response.QuotaCheckResponse;
import com.backend.documentservice.dto.response.QuotaConsumeResponse;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;

import java.util.UUID;

@FeignClient(
        name = "subscription-service",
        url = "${app.subscription-service.url:http://subscription-service:8084/api/subscription}",
        configuration = FeignClientConfig.class
)
public interface SubscriptionClient {

    @GetMapping("/internal/quota/check")
    ApiResponse<QuotaCheckResponse> checkQuota(
            @RequestParam("userId") UUID userId,
            @RequestParam("featureKey") String featureKey
    );

    @PostMapping("/internal/quota/consume")
    ApiResponse<QuotaConsumeResponse> consumeQuota(@RequestBody InternalQuotaRequest request);
}
