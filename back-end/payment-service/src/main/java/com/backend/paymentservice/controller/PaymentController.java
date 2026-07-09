package com.backend.paymentservice.controller;

import com.backend.paymentservice.dto.request.CancelPaymentRequest;
import com.backend.paymentservice.dto.request.PaymentRequest;
import com.backend.paymentservice.dto.response.ApiResponse;
import com.backend.paymentservice.dto.response.PaymentResponse;
import com.backend.paymentservice.service.PaymentService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping
@RequiredArgsConstructor
@Slf4j
public class PaymentController {

    private final PaymentService paymentService;

    @PostMapping("/create")
    public ApiResponse<PaymentResponse> createPaymentLink(
            @Valid @RequestBody PaymentRequest request) {
        log.info("[payment-service] Nhận yêu cầu tạo Payment Link (Provider: {}): {}", request.getPaymentProvider(), request);
        return ApiResponse.<PaymentResponse>builder()
                .data(paymentService.createPaymentLink(request))
                .build();
    }

    @GetMapping("/{paymentCode}")
    public ApiResponse<Map<String, Object>> getPaymentLinkInformation(@PathVariable Long paymentCode) {
        log.info("[payment-service] Nhận yêu cầu lấy thông tin thanh toán cho mã: {}", paymentCode);
        return ApiResponse.<Map<String, Object>>builder()
                .data(paymentService.getPaymentLinkInformation(paymentCode))
                .build();
    }

    @PostMapping("/cancel")
    public ApiResponse<Map<String, Object>> cancelPaymentLink(@Valid @RequestBody CancelPaymentRequest request) {
        log.info("[payment-service] Nhận yêu cầu hủy thanh toán cho mã: {}, lý do: {}", request.getPaymentCode(), request.getReason());
        return ApiResponse.<Map<String, Object>>builder()
                .data(paymentService.cancelPaymentLink(request.getPaymentCode(), request.getReason()))
                .build();
    }

    @PostMapping("/webhook/stripe")
    public ResponseEntity<Map<String, Object>> handleStripeWebhook(
            @RequestBody String payload,
            @RequestHeader(value = "Stripe-Signature", required = false) String sigHeader) {
        log.info("[payment-service] Nhận webhook riêng Stripe. SigHeader={}", sigHeader);
        Map<String, Object> result = paymentService.verifyStripeWebhook(payload, sigHeader);
        return ResponseEntity.ok(result);
    }

    @PostMapping("/webhook/payos")
    public ResponseEntity<Map<String, Object>> handlePayOSWebhook(
            @RequestBody String payload,
            @RequestHeader(value = "x-payos-signature", required = false) String sigHeader) {
        log.info("[payment-service] Nhận webhook riêng PayOS. SigHeader={}", sigHeader);
        Map<String, Object> result = paymentService.verifyPayOSWebhook(payload, sigHeader);
        return ResponseEntity.ok(result);
    }
}
