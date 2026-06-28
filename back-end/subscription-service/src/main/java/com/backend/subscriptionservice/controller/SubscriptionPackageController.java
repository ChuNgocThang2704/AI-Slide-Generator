package com.backend.subscriptionservice.controller;

import com.backend.subscriptionservice.dto.response.ApiResponse;
import com.backend.subscriptionservice.dto.response.PackageResponse;
import com.backend.subscriptionservice.service.SubscriptionPackageService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/packages")
@RequiredArgsConstructor
public class SubscriptionPackageController {

    private final SubscriptionPackageService packageService;

    @GetMapping
    public ApiResponse<List<PackageResponse>> getPackages() {
        return ApiResponse.<List<PackageResponse>>builder()
                .data(packageService.getPackages())
                .build();
    }

    @GetMapping("/{code}")
    public ApiResponse<PackageResponse> getPackageByCode(@PathVariable String code) {
        return ApiResponse.<PackageResponse>builder()
                .data(packageService.getPackageByCode(code))
                .build();
    }
}
