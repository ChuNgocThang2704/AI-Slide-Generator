package com.backend.userservice.constant;

public class Status {
    public interface USER_STATUS {
        int CREATED = 0;      // Mới tạo
        int VERIFIED = 1;     // Đã xác thực
        int ACTIVE = 2;       // Hoạt động
        int DEACTIVATED = 3;  // Dừng sử dụng
    }
}