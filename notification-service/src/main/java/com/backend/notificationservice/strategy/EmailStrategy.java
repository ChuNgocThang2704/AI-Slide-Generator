package com.backend.notificationservice.strategy;

import java.util.Map;

public interface EmailStrategy {
    String getSubject(Map<String, Object> payload);
    String getTemplateName();
}
