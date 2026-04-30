package com.backend.gateway;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.context.annotation.Bean;
import reactor.core.publisher.Mono;
import lombok.extern.slf4j.Slf4j;

@SpringBootApplication
@Slf4j
public class ApiGatewayApplication {

	public static void main(String[] args) {
		SpringApplication.run(ApiGatewayApplication.class, args);
	}

	@Bean
	public GlobalFilter customGlobalFilter() {
		return (exchange, chain) -> {
			log.info("GATEWAY RECEIVING REQUEST: {} {}", 
                exchange.getRequest().getMethod(), 
                exchange.getRequest().getURI());
			return chain.filter(exchange).then(Mono.fromRunnable(() -> {
				log.info("GATEWAY RESPONDING WITH STATUS: {}", 
                    exchange.getResponse().getStatusCode());
			}));
		};
	}
}
