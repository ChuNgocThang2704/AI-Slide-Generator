package com.backend.gateway.filters;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.ReactiveStringRedisTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

import java.time.Duration;

@RestController
@RequiredArgsConstructor
@Slf4j
public class RedisTestController {

    private final ReactiveStringRedisTemplate redisTemplate;

    @GetMapping("/redis")
    public Mono<String> testRedisConnection() {
        String key = "gateway_test_key";
        String value = "Connected_at_" + System.currentTimeMillis();

        return redisTemplate.opsForValue().set(key, value)
                .then(redisTemplate.opsForValue().get(key))
                .map(result -> "Redis Status: SUCCESS. Retrieved value: " + result)
                .timeout(Duration.ofSeconds(5)) // Giới hạn thời gian chờ kết nối
                .onErrorResume(e -> {
                    log.error("Redis connection failed: {}", e.getMessage());
                    return Mono.just("Redis Status: FAILED. Error: " + e.getMessage());
                });
    }
}