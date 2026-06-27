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
import vn.payos.model.v2.paymentRequests.PaymentLink;
import vn.payos.model.webhooks.Webhook;
import vn.payos.model.webhooks.WebhookData;

import java.util.HashMap;
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
        log.info("[payment-service] Nhận yêu cầu tạo link thanh toán: {}", request);
        return ApiResponse.<PaymentResponse>builder()
                .data(paymentService.createPaymentLink(request))
                .build();
    }

    @GetMapping("/{paymentCode}")
    public ApiResponse<PaymentLink> getPaymentLinkInformation(@PathVariable Long paymentCode) {
        log.info("[payment-service] Nhận yêu cầu lấy thông tin thanh toán cho mã: {}", paymentCode);
        return ApiResponse.<PaymentLink>builder()
                .data(paymentService.getPaymentLinkInformation(paymentCode))
                .build();
    }

    @PostMapping("/cancel")
    public ApiResponse<PaymentLink> cancelPaymentLink(@Valid @RequestBody CancelPaymentRequest request) {
        log.info("[payment-service] Nhận yêu cầu hủy thanh toán cho mã: {}, lý do: {}", request.getPaymentCode(), request.getReason());
        return ApiResponse.<PaymentLink>builder()
                .data(paymentService.cancelPaymentLink(request.getPaymentCode(), request.getReason()))
                .build();
    }

    @PostMapping("/webhook")
    public ResponseEntity<Map<String, Object>> handleWebhook(@RequestBody Webhook webhook) {
        log.info("[payment-service] Nhận webhook từ PayOS: {}", webhook);
        WebhookData verifiedData = paymentService.verifyWebhook(webhook);

        log.info("[payment-service] Xác thực thành công webhook. Mã thanh toán: {}, Số tiền: {}, Mô tả: {}, Mã giao dịch ngân hàng: {}",
                verifiedData.getOrderCode(),
                verifiedData.getAmount(),
                verifiedData.getDescription(),
                verifiedData.getReference());

        Map<String, Object> response = new HashMap<>();
        response.put("code", "00");
        response.put("desc", "success");
        response.put("data", verifiedData);

        return ResponseEntity.ok(response);
    }
}
