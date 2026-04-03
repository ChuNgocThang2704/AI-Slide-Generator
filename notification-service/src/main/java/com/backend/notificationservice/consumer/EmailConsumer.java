package com.backend.notificationservice.consumer;

import com.backend.notificationservice.dto.EmailRequest;
import com.backend.notificationservice.service.MailService;
import com.backend.notificationservice.strategy.EmailStrategy;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;
import java.util.Map;

@Component
@RequiredArgsConstructor
@Slf4j
public class EmailConsumer {
    private final MailService mailService;
    private final Map<String, EmailStrategy> strategyMap;

    @RabbitListener(queues = "${app.rabbitmq.queue}")
    public void receive(EmailRequest request) {
        log.info("Received email request for: {} with type: {}", request.getTo(), request.getType());

        EmailStrategy strategy = strategyMap.get(request.getType());

        if (strategy != null) {
            mailService.sendHtmlMail(
                    request.getTo(),
                    strategy.getSubject(request.getPayload()),
                    strategy.getTemplateName(),
                    request.getPayload()
            );
        } else {
            log.warn("No strategy found for email type: {}", request.getType());
        }
    }
}