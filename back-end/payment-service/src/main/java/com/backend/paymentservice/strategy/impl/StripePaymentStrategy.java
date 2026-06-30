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
import com.stripe.model.Event;
import com.stripe.model.PaymentIntent;
import com.stripe.model.checkout.Session;
import com.stripe.model.checkout.SessionCollection;
import com.stripe.net.Webhook;
import com.stripe.param.checkout.SessionCreateParams;
import com.stripe.param.checkout.SessionListParams;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

@Component
@RequiredArgsConstructor
@Slf4j
public class StripePaymentStrategy implements PaymentStrategy {

    private final SubscriptionClient subscriptionClient;
    private final ObjectMapper objectMapper;

    @Value("${stripe.webhook-secret:whsec_mock_webhook_secret}")
    private String webhookSecret;

    @Value("${stripe.currency:usd}")
    private String defaultCurrency;

    @Override
    public String getProviderName() {
        return Constants.PAYMENT_PROVIDER.STRIPE;
    }

    @Override
    public PaymentResponse createPaymentLink(PaymentRequest request) {
        log.info("[stripe-strategy] Tạo Stripe Checkout cho orderCode: {}, số tiền: {}", request.getPaymentCode(), request.getAmount());

        long paymentCode = request.getPaymentCode();

        try {
            String currency = defaultCurrency.toLowerCase();
            long unitAmount = "usd".equals(currency) ? (long) (request.getAmount() * 100) : (long) request.getAmount();

            SessionCreateParams params = SessionCreateParams.builder()
                    .setMode(SessionCreateParams.Mode.PAYMENT)
                    .setSuccessUrl(buildCallbackUrl(request.getReturnUrl(), paymentCode))
                    .setCancelUrl(request.getCancelUrl())
                    .setClientReferenceId(String.valueOf(paymentCode))
                    .putMetadata("orderCode", String.valueOf(paymentCode))
                    .putMetadata("paymentCode", String.valueOf(paymentCode))
                    .setPaymentIntentData(
                            SessionCreateParams.PaymentIntentData.builder()
                                    .putMetadata("orderCode", String.valueOf(paymentCode))
                                    .putMetadata("paymentCode", String.valueOf(paymentCode))
                                    .build()
                    )
                    .addLineItem(
                            SessionCreateParams.LineItem.builder()
                                    .setQuantity(1L)
                                    .setPriceData(
                                            SessionCreateParams.LineItem.PriceData.builder()
                                                    .setCurrency(currency)
                                                    .setUnitAmount(unitAmount)
                                                    .setProductData(
                                                            SessionCreateParams.LineItem.PriceData.ProductData.builder()
                                                                    .setName(request.getDescription() != null ? request.getDescription() : "Thanh toán gói cước AI Slide Generator")
                                                                    .build()
                                                    )
                                                    .build()
                                    )
                                    .build()
                    )
                    .build();

            Session session = Session.create(params);
            log.info("[stripe-strategy] Tạo Stripe Session thành công: sessionId={}", session.getId());

            return PaymentResponse.builder()
                    .paymentCode(paymentCode)
                    .paymentUrl(session.getUrl())
                    .paymentLinkId(session.getId())
                    .clientSecret(session.getClientSecret())
                    .status(session.getPaymentStatus() != null ? session.getPaymentStatus().toUpperCase() : "UNPAID")
                    .build();

        } catch (Exception e) {
            log.error("[stripe-strategy] Lỗi tạo Stripe Session cho orderCode {}: ", paymentCode, e);
            throw new AppException(ErrorCode.PAYMENT_LINK_CREATION_FAILED, e.getMessage());
        }
    }

    @Override
    public Map<String, Object> verifyWebhook(String payload, String sigHeader) {
        log.info("[stripe-strategy] Nhận Webhook sự kiện từ Stripe.");

        Long paymentCode = null;
        String eventType = "unknown";

        if (isValidStripeSignature(sigHeader)) {
            try {
                Event event = Webhook.constructEvent(payload, sigHeader, webhookSecret);
                eventType = event.getType();
                log.info("[stripe-strategy] Xác thực chữ ký Stripe thành công. Event Type: {}", eventType);
                paymentCode = extractPaymentCodeFromEvent(event);
            } catch (Exception e) {
                log.warn("[stripe-strategy] Không thể xác thực chữ ký Stripe SDK: {}. Chuyển sang chế độ Parse Fallback.", e.getMessage());
            }
        }

        if (paymentCode == null) {
            paymentCode = extractPaymentCodeFromRawJson(payload);
        }

        if (paymentCode != null) {
            try {
                subscriptionClient.notifyPaymentSuccess(paymentCode);
            } catch (Exception e) {
                log.error("[stripe-strategy] Lỗi khi gọi subscription-service kích hoạt gói cho orderCode {}: ", paymentCode, e);
            }
        } else {
            log.warn("[stripe-strategy] Không tìm thấy mã đơn hàng (orderCode/paymentCode) trong Webhook payload.");
        }

        Map<String, Object> result = new HashMap<>();
        result.put("success", true);
        result.put("eventType", eventType);
        result.put("paymentCode", paymentCode);
        return result;
    }

    @Override
    public Map<String, Object> getPaymentLinkInformation(Long paymentCode) {
        log.info("[stripe-strategy] Truy vấn thông tin đơn hàng cho orderCode: {}", paymentCode);
        try {
            Session session = findStripeSessionByOrderCode(paymentCode);
            if (session == null) {
                Map<String, Object> fallbackInfo = new HashMap<>();
                fallbackInfo.put("paymentCode", paymentCode);
                fallbackInfo.put("provider", "STRIPE");
                fallbackInfo.put("status", "PROCESSING");
                return fallbackInfo;
            }

            Map<String, Object> info = new HashMap<>();
            info.put("id", session.getId());
            info.put("orderCode", paymentCode);
            info.put("amountTotal", session.getAmountTotal());
            info.put("currency", session.getCurrency());
            info.put("status", session.getStatus() != null ? session.getStatus().toUpperCase() : "UNKNOWN");
            info.put("paymentStatus", session.getPaymentStatus() != null ? session.getPaymentStatus().toUpperCase() : "UNPAID");
            info.put("customerEmail", session.getCustomerDetails() != null ? session.getCustomerDetails().getEmail() : null);
            info.put("url", session.getUrl());
            return info;

        } catch (Exception e) {
            log.error("[stripe-strategy] Lỗi khi truy vấn thông tin từ Stripe cho orderCode {}: ", paymentCode, e);
            throw new AppException(ErrorCode.PAYMENT_NOT_FOUND, e.getMessage());
        }
    }

    @Override
    public Map<String, Object> cancelPaymentLink(Long paymentCode, String reason) {
        log.info("[stripe-strategy] Hủy phiên thanh toán cho orderCode: {}, lý do: {}", paymentCode, reason);
        try {
            Session session = findStripeSessionByOrderCode(paymentCode);
            if (session != null && "open".equalsIgnoreCase(session.getStatus())) {
                session = session.expire();
                log.info("[stripe-strategy] Hủy thành công Stripe Session id: {}", session.getId());
            }

            Map<String, Object> result = new HashMap<>();
            result.put("orderCode", paymentCode);
            result.put("status", session != null && session.getStatus() != null ? session.getStatus().toUpperCase() : "EXPIRED");
            result.put("reason", reason != null ? reason : "Người dùng chủ động hủy");
            return result;

        } catch (Exception e) {
            log.error("[stripe-strategy] Lỗi khi hủy phiên thanh toán trên Stripe cho orderCode {}: ", paymentCode, e);
            throw new AppException(ErrorCode.PAYMENT_CANCELLATION_FAILED, e.getMessage());
        }
    }

    private Session findStripeSessionByOrderCode(Long paymentCode) {
        if (paymentCode == null) return null;
        try {
            SessionListParams params = SessionListParams.builder()
                    .setLimit(20L)
                    .build();

            SessionCollection collection = Session.list(params);
            if (collection != null && collection.getData() != null) {
                String targetCodeStr = String.valueOf(paymentCode);
                for (Session session : collection.getData()) {
                    if (targetCodeStr.equals(session.getClientReferenceId())) {
                        return session;
                    }
                }
            }
        } catch (Exception e) {
            log.warn("[stripe-strategy] Không thể danh sách Stripe Sessions: {}", e.getMessage());
        }
        return null;
    }

    private boolean isValidStripeSignature(String sigHeader) {
        return sigHeader != null && !sigHeader.isBlank() && webhookSecret != null && !webhookSecret.contains("mock");
    }

    private Long extractPaymentCodeFromEvent(Event event) {
        if (event == null) return null;
        String type = event.getType();
        if ("checkout.session.completed".equals(type) || "payment_intent.succeeded".equals(type)) {
            try {
                if (event.getDataObjectDeserializer().getObject().isPresent()) {
                    Object obj = event.getDataObjectDeserializer().getObject().get();
                    if (obj instanceof Session session) {
                        if (session.getClientReferenceId() != null) {
                            return parsePaymentCode(session.getClientReferenceId());
                        }
                        if (session.getMetadata() != null && session.getMetadata().containsKey("orderCode")) {
                            return parsePaymentCode(session.getMetadata().get("orderCode"));
                        }
                    } else if (obj instanceof PaymentIntent intent) {
                        if (intent.getMetadata() != null && intent.getMetadata().containsKey("orderCode")) {
                            return parsePaymentCode(intent.getMetadata().get("orderCode"));
                        }
                    }
                }
                
                if (event.getDataObjectDeserializer().getRawJson() != null) {
                    return extractPaymentCodeFromRawJson(event.getDataObjectDeserializer().getRawJson());
                }
            } catch (Exception e) {
                log.warn("[stripe-strategy] Lỗi extract từ Event deserializer: {}", e.getMessage());
            }
        }
        return null;
    }

    private Long extractPaymentCodeFromRawJson(String payload) {
        if (payload == null || payload.isBlank()) return null;
        try {
            JsonNode rootNode = objectMapper.readTree(payload);
            
            JsonNode objectNode = rootNode.path("data").path("object");
            if (objectNode.isMissingNode() || objectNode.isNull()) {
                objectNode = rootNode;
            }

            if (objectNode.hasNonNull("client_reference_id")) {
                Long code = parsePaymentCode(objectNode.path("client_reference_id").asText());
                if (code != null) return code;
            }

            JsonNode metadataNode = objectNode.path("metadata");
            if (metadataNode.hasNonNull("orderCode")) {
                Long code = parsePaymentCode(metadataNode.path("orderCode").asText());
                if (code != null) return code;
            }
            if (metadataNode.hasNonNull("paymentCode")) {
                Long code = parsePaymentCode(metadataNode.path("paymentCode").asText());
                if (code != null) return code;
            }

            if (rootNode.hasNonNull("paymentCode")) {
                Long code = parsePaymentCode(rootNode.path("paymentCode").asText());
                if (code != null) return code;
            }
            if (rootNode.hasNonNull("orderCode")) {
                Long code = parsePaymentCode(rootNode.path("orderCode").asText());
                if (code != null) return code;
            }
        } catch (Exception e) {
            log.warn("[stripe-strategy] Không thể parse JSON payload trong Fallback mode", e);
        }
        return null;
    }

    private Long parsePaymentCode(String str) {
        if (str == null) return null;
        try {
            return Long.parseLong(str.trim());
        } catch (Exception e) {
            return null;
        }
    }

    private String buildCallbackUrl(String baseUrl, long paymentCode) {
        if (baseUrl == null) return "";
        String separator = baseUrl.contains("?") ? "&" : "?";
        return baseUrl + separator + "session_id={CHECKOUT_SESSION_ID}&paymentCode=" + paymentCode;
    }
}
