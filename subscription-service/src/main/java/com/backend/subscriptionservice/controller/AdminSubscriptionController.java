package com.backend.subscriptionservice.controller;

import com.backend.subscriptionservice.dto.request.CreatePackageRequest;
import com.backend.subscriptionservice.dto.request.FeatureRequest;
import com.backend.subscriptionservice.dto.request.UpdatePackageRequest;
import com.backend.subscriptionservice.dto.response.ApiResponse;
import com.backend.subscriptionservice.dto.response.PackageResponse;
import com.backend.subscriptionservice.service.SubscriptionPackageService;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/admin")
@PreAuthorize("hasRole('ADMIN')")
@RequiredArgsConstructor
public class AdminSubscriptionController {

    private final SubscriptionPackageService packageService;

    @PostMapping("/packages")
    public ApiResponse<PackageResponse> createPackage(@RequestBody CreatePackageRequest request) {
        return ApiResponse.<PackageResponse>builder()
                .message("Subscription package created successfully")
                .data(packageService.createPackage(request))
                .build();
    }

    @PutMapping("/packages/{id}")
    public ApiResponse<PackageResponse> updatePackage(@PathVariable UUID id, @RequestBody UpdatePackageRequest request) {
        return ApiResponse.<PackageResponse>builder()
                .message("Subscription package updated successfully")
                .data(packageService.updatePackage(id, request))
                .build();
    }

    @DeleteMapping("/packages/{id}")
    public ApiResponse<Void> deletePackage(@PathVariable UUID id) {
        packageService.deletePackage(id);
        return ApiResponse.<Void>builder()
                .message("Subscription package soft-deleted successfully")
                .build();
    }

    @PostMapping("/packages/{packageId}/features")
    public ApiResponse<Void> addFeature(@PathVariable UUID packageId, @RequestBody FeatureRequest request) {
        packageService.addFeature(packageId, request);
        return ApiResponse.<Void>builder()
                .message("Package feature added successfully")
                .build();
    }

    @PutMapping("/packages/{packageId}/features/{featureKey}")
    public ApiResponse<Void> updateFeature(
            @PathVariable UUID packageId,
            @PathVariable String featureKey,
            @RequestBody FeatureRequest request) {
        packageService.updateFeature(packageId, featureKey, request);
        return ApiResponse.<Void>builder()
                .message("Package feature limit updated successfully")
                .build();
    }

    @DeleteMapping("/packages/{packageId}/features/{featureKey}")
    public ApiResponse<Void> deleteFeature(@PathVariable UUID packageId, @PathVariable String featureKey) {
        packageService.deleteFeature(packageId, featureKey);
        return ApiResponse.<Void>builder()
                .message("Package feature limit deleted successfully")
                .build();
    }
}
