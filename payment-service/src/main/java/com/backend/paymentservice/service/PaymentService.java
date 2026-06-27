package com.backend.paymentservice.service;

import com.backend.paymentservice.dto.request.PaymentRequest;
import com.backend.paymentservice.dto.response.PaymentResponse;
import com.backend.paymentservice.exception.AppException;
import com.backend.paymentservice.exception.ErrorCode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import vn.payos.PayOS;
import vn.payos.model.v2.paymentRequests.CreatePaymentLinkRequest;
import vn.payos.model.v2.paymentRequests.CreatePaymentLinkResponse;
import vn.payos.model.v2.paymentRequests.PaymentLink;
import vn.payos.model.webhooks.Webhook;
import vn.payos.model.webhooks.WebhookData;

import java.util.Random;

@Service
@RequiredArgsConstructor
@Slf4j
public class PaymentService {

    private final PayOS payOS;
    private final Random random = new Random();

    public PaymentResponse createPaymentLink(PaymentRequest request) {
        log.info("[payment-service] Tạo link thanh toán cho số tiền: {}", request.getAmount());

        long paymentCode = generatePaymentCode();

        try {
            CreatePaymentLinkRequest paymentLinkRequest = CreatePaymentLinkRequest.builder()
                    .orderCode(paymentCode)
                    .amount(request.getAmount())
                    .description(request.getDescription())
                    .returnUrl(request.getReturnUrl())
                    .cancelUrl(request.getCancelUrl())
                    .build();

            CreatePaymentLinkResponse payosResponse = payOS.paymentRequests().create(paymentLinkRequest);

            String statusStr = payosResponse.getStatus() != null ? payosResponse.getStatus().name() : "PENDING";

            return PaymentResponse.builder()
                    .paymentCode(paymentCode)
                    .paymentUrl(payosResponse.getCheckoutUrl())
                    .paymentLinkId(payosResponse.getPaymentLinkId())
                    .status(statusStr)
                    .build();

        } catch (Exception e) {
            log.error("[payment-service] Lỗi khi tạo link thanh toán từ PayOS: ", e);
            throw new AppException(ErrorCode.PAYMENT_LINK_CREATION_FAILED, e.getMessage());
        }
    }

    public PaymentLink getPaymentLinkInformation(Long paymentCode) {
        log.info("[payment-service] Lấy thông tin thanh toán cho mã: {}", paymentCode);
        try {
            return payOS.paymentRequests().get(paymentCode);
        } catch (Exception e) {
            log.error("[payment-service] Lỗi khi lấy thông tin thanh toán từ PayOS cho mã: {}", paymentCode, e);
            throw new AppException(ErrorCode.PAYMENT_NOT_FOUND, e.getMessage());
        }
    }

    public PaymentLink cancelPaymentLink(Long paymentCode, String reason) {
        log.info("[payment-service] Yêu cầu hủy thanh toán cho mã: {}, lý do: {}", paymentCode, reason);
        try {
            String cancelReason = reason != null ? reason : "Khách hàng yêu cầu hủy";
            return payOS.paymentRequests().cancel(paymentCode, cancelReason);
        } catch (Exception e) {
            log.error("[payment-service] Lỗi khi hủy thanh toán trên PayOS cho mã: {}", paymentCode, e);
            throw new AppException(ErrorCode.PAYMENT_CANCELLATION_FAILED, e.getMessage());
        }
    }

    public WebhookData verifyWebhook(Webhook webhook) {
        log.info("[payment-service] Nhận webhook từ PayOS, bắt đầu xác thực chữ ký");
        try {
            return payOS.webhooks().verify(webhook);
        } catch (Exception e) {
            log.error("[payment-service] Xác thực chữ ký webhook thất bại: ", e);
            throw new AppException(ErrorCode.INVALID_WEBHOOK_SIGNATURE, e.getMessage());
        }
    }

    private long generatePaymentCode() {
        long timestampPart = System.currentTimeMillis() % 10000000000L;
        long randomPart = random.nextInt(1000000);
        return timestampPart * 1000000L + randomPart;
    }
}
