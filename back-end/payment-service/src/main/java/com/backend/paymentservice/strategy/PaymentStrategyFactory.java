package com.backend.paymentservice.strategy;

import com.backend.paymentservice.exception.AppException;
import com.backend.paymentservice.exception.ErrorCode;
import com.backend.paymentservice.util.Constants;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

@Component
public class PaymentStrategyFactory {

    private final Map<String, PaymentStrategy> strategies;

    public PaymentStrategyFactory(List<PaymentStrategy> strategyList) {
        this.strategies = strategyList.stream()
                .collect(Collectors.toMap(
                        strategy -> strategy.getProviderName().toUpperCase(),
                        Function.identity()
                ));
    }

    public PaymentStrategy getStrategy(String provider) {
        if (provider == null || provider.isBlank()) {
            provider = Constants.PAYMENT_PROVIDER.STRIPE; // Mặc định là STRIPE nếu không truyền
        }
        PaymentStrategy strategy = strategies.get(provider.toUpperCase());
        if (strategy == null) {
            throw new AppException(ErrorCode.PAYMENT_LINK_CREATION_FAILED, "Cổng thanh toán không được hỗ trợ: " + provider);
        }
        return strategy;
    }
}
