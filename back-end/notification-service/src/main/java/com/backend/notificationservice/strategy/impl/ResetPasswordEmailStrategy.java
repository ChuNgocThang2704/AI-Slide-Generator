package com.backend.notificationservice.strategy.impl;

import com.backend.notificationservice.strategy.EmailStrategy;
import org.springframework.stereotype.Component;

import java.util.Map;

@Component("RESET_PASSWORD")
public class ResetPasswordEmailStrategy implements EmailStrategy {
    @Override
    public String getSubject(Map<String, Object> payload) {
        return "[PSlideAI] Yêu cầu đặt lại mật khẩu";
    }

    @Override
    public String getTemplateName() {
        return "reset-password-email";
    }
}
