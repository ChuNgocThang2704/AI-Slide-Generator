package com.backend.subscriptionservice.util;

public class Constants {

    public interface SUBSCRIPTION_ACTION {
        int REGISTER = 0;
        int UPGRADE = 1;
        int DOWNGRADE = 2;
        int CANCEL = 3;
        int EXTEND = 4;
    }

    public interface BILLING_CYCLE {
        int MONTHLY = 0;
        int YEARLY = 1;
    }

    public interface SUBSCRIPTION_STATUS {
        int PENDING_PAYMENT = 0;
        int ACTIVE = 1;
        int EXPIRED = 2;
        int CANCELED = 3;
    }

    public interface FEATURE_KEY {
        String MAX_SLIDES_PER_DAY = "MAX_SLIDES_PER_DAY";
        String MAX_IMAGES_PER_SLIDE = "MAX_IMAGES_PER_SLIDE";
        String ALLOW_EXPORT_PDF = "ALLOW_EXPORT_PDF";
        String ALLOW_CUSTOM_TEMPLATE = "ALLOW_CUSTOM_TEMPLATE";
    }

    public interface PACKAGE_CODE {
        String FREE = "FREE";
        String PRO = "PRO";
        String ULTRA = "ULTRA";
    }

    public interface PAYMENT_PROVIDER {
        String STRIPE = "STRIPE";
        String PAYOS = "PAYOS";
    }
}
