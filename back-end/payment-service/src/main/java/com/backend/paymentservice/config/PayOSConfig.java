package com.backend.paymentservice.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import vn.payos.PayOS;

@Configuration
public class PayOSConfig {

    @Value("${payos.client-id:mock_client_id}")
    private String clientId;

    @Value("${payos.api-key:mock_api_key}")
    private String apiKey;

    @Value("${payos.checksum-key:mock_checksum_key}")
    private String checksumKey;

    @Bean
    public PayOS payOS() {
        return new PayOS(clientId, apiKey, checksumKey);
    }
}
