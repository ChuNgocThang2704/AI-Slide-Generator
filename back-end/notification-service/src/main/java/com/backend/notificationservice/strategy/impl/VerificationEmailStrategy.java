package com.backend.notificationservice.strategy.impl;

import com.backend.notificationservice.strategy.EmailStrategy;
import org.springframework.stereotype.Component;

import java.util.Map;

@Component("REGISTRATION_VERIFY")
public class VerificationEmailStrategy implements EmailStrategy {
    @Override
    public String getSubject(Map<String, Object> payload) {
        return "[AI Slide] Mã xác thực đăng ký tài khoản";
    }

    @Override
    public String getTemplateName() {
        return "verification-email";
    }
}
