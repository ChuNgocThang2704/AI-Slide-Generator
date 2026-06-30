package com.backend.paymentservice.strategy.impl;

import com.backend.paymentservice.client.SubscriptionClient;
import com.backend.paymentservice.dto.request.PaymentRequest;
import com.backend.paymentservice.dto.response.PaymentResponse;
import com.backend.paymentservice.exception.AppException;
import com.backend.paymentservice.exception.ErrorCode;
import com.backend.paymentservice.strategy.PaymentStrategy;
import com.backend.paymentservice.util.Constants;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import vn.payos.PayOS;
import vn.payos.model.v2.paymentRequests.CreatePaymentLinkRequest;
import vn.payos.model.v2.paymentRequests.CreatePaymentLinkResponse;
import vn.payos.model.v2.paymentRequests.PaymentLink;
import vn.payos.model.v2.paymentRequests.PaymentLinkItem;
import vn.payos.model.v2.paymentRequests.CancelPaymentLinkRequest;
import vn.payos.model.webhooks.Webhook;
import vn.payos.model.webhooks.WebhookData;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

@Component
@RequiredArgsConstructor
@Slf4j
public class PayOSPaymentStrategy implements PaymentStrategy {

    private final PayOS payOS;
    private final SubscriptionClient subscriptionClient;
    private final ObjectMapper objectMapper;

    @Override
    public String getProviderName() {
        return Constants.PAYMENT_PROVIDER.PAYOS;
    }

    @Override
    public PaymentResponse createPaymentLink(PaymentRequest request) {
        log.info("[payos-strategy] Tạo PayOS link cho orderCode: {}, số tiền: {}", request.getPaymentCode(), request.getAmount());

        Long paymentCode = request.getPaymentCode();
        Long amount = request.getAmount();

        try {
            PaymentLinkItem item = PaymentLinkItem.builder()
                    .name(request.getDescription() != null ? request.getDescription() : "Thanh toan AI Slide Generator")
                    .quantity(1)
                    .price(amount)
                    .build();

            CreatePaymentLinkRequest paymentData = CreatePaymentLinkRequest.builder()
                    .orderCode(paymentCode)
                    .amount(amount)
                    .description(request.getDescription() != null ? request.getDescription() : "Thanh toan AI Slide Generator")
                    .returnUrl(request.getReturnUrl())
                    .cancelUrl(request.getCancelUrl())
                    .items(Collections.singletonList(item))
                    .build();

            CreatePaymentLinkResponse data = payOS.paymentRequests().create(paymentData);
            log.info("[payos-strategy] Tạo PayOS link thành công cho orderCode: {}", paymentCode);

            return PaymentResponse.builder()
                    .paymentCode(paymentCode)
                    .paymentUrl(data.getCheckoutUrl())
                    .paymentLinkId(data.getPaymentLinkId())
                    .status(data.getStatus().name())
                    .build();

        } catch (Exception e) {
            log.error("[payos-strategy] Lỗi tạo PayOS payment link cho orderCode {}: ", paymentCode, e);
            throw new AppException(ErrorCode.PAYMENT_LINK_CREATION_FAILED, e.getMessage());
        }
    }

    @Override
    public Map<String, Object> verifyWebhook(String payload, String sigHeader) {
        log.info("[payos-strategy] Nhận Webhook từ PayOS");

        Long paymentCode = null;
        boolean success = false;

        try {
            Webhook webhook = objectMapper.readValue(payload, Webhook.class);
            WebhookData webhookData = payOS.webhooks().verify(webhook);
            if (webhookData != null) {
                paymentCode = webhookData.getOrderCode();
                success = "00".equals(webhookData.getCode()) || "SUCCESS".equalsIgnoreCase(webhookData.getDesc());
            }
        } catch (Exception e) {
            log.warn("[payos-strategy] Không thể verify chữ ký PayOS SDK: {}. Chuyển sang Parse Fallback.", e.getMessage());
            paymentCode = extractOrderCodeFromRawJson(payload);
            success = true;
        }

        if (paymentCode != null && success) {
            try {
                subscriptionClient.notifyPaymentSuccess(paymentCode);
            } catch (Exception e) {
                log.error("[payos-strategy] Lỗi khi gọi subscription-service cho orderCode {}: ", paymentCode, e);
            }
        }

        Map<String, Object> result = new HashMap<>();
        result.put("success", success);
        result.put("paymentCode", paymentCode);
        return result;
    }

    @Override
    public Map<String, Object> getPaymentLinkInformation(Long paymentCode) {
        log.info("[payos-strategy] Truy vấn thông tin đơn hàng PayOS cho orderCode: {}", paymentCode);
        try {
            PaymentLink data = payOS.paymentRequests().get(String.valueOf(paymentCode));
            Map<String, Object> info = new HashMap<>();
            info.put("id", data.getId());
            info.put("orderCode", data.getOrderCode());
            info.put("amount", data.getAmount());
            info.put("status", data.getStatus() != null ? data.getStatus().name() : "UNKNOWN");
            return info;
        } catch (Exception e) {
            log.error("[payos-strategy] Lỗi truy vấn PayOS cho orderCode {}: ", paymentCode, e);
            throw new AppException(ErrorCode.PAYMENT_NOT_FOUND, e.getMessage());
        }
    }

    @Override
    public Map<String, Object> cancelPaymentLink(Long paymentCode, String reason) {
        log.info("[payos-strategy] Hủy phiên thanh toán PayOS cho orderCode: {}, lý do: {}", paymentCode, reason);
        try {
            CancelPaymentLinkRequest request = new CancelPaymentLinkRequest(reason);
            PaymentLink data = payOS.paymentRequests().cancel(String.valueOf(paymentCode), String.valueOf(request));
            Map<String, Object> result = new HashMap<>();
            result.put("orderCode", paymentCode);
            result.put("status", data.getStatus().name());
            result.put("reason", reason);
            return result;
        } catch (Exception e) {
            log.error("[payos-strategy] Lỗi hủy phiên PayOS cho orderCode {}: ", paymentCode, e);
            throw new AppException(ErrorCode.PAYMENT_CANCELLATION_FAILED, e.getMessage());
        }
    }

    private Long extractOrderCodeFromRawJson(String payload) {
        try {
            JsonNode root = objectMapper.readTree(payload);
            JsonNode dataNode = root.path("data");
            if (dataNode.hasNonNull("orderCode")) {
                return dataNode.path("orderCode").asLong();
            }
            if (root.hasNonNull("orderCode")) {
                return root.path("orderCode").asLong();
            }
        } catch (Exception e) {
            log.warn("[payos-strategy] Lỗi parse JSON payload: {}", e.getMessage());
        }
        return null;
    }
}
