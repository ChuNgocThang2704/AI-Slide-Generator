package com.backend.documentservice.util;

public class Constants {

    public interface PROJECT_STATUS {
        int DRAFT = 0;
        int REVIEWING = 1;
        int PROCESSING = 2;
        int DONE = 3;
        int FAILED = 4;
    }

    public interface TASK_TYPE {
        int EXTRACT_TEXT = 0;
        int GEN_IMAGE = 1;
        int RENDER_PPTX = 2;
    }

    public interface TASK_STATUS {
        int PENDING = 0;
        int PROCESSING = 1;
        int SUCCESS = 2;
        int FAILED = 3;
    }

    public interface EXPORT_TYPE {
        int PPTX = 0;
        int PDF = 1;
    }

    public interface DOCUMENT_TYPE {
        int PDF = 0;
        int DOCX = 1;
        int TEXT_PROMPT = 2;
    }

    public interface USER_ROLES {
        String ADMIN = "ADMIN";
        String USER_FREE = "USER_FREE";
        String USER_PRO = "USER_PRO";
        String USER_EXTRA = "USER_EXTRA";
    }
}
