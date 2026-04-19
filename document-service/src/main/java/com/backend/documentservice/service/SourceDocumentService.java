package com.backend.documentservice.service;

import com.backend.documentservice.dto.response.SourceDocumentResponse;
import com.backend.documentservice.entity.SourceDocument;
import com.backend.documentservice.exception.AppException;
import com.backend.documentservice.exception.ErrorCode;
import com.backend.documentservice.mapper.SourceDocumentMapper;
import com.backend.documentservice.repository.SourceDocumentRepository;
import com.backend.documentservice.util.Constants;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
public class SourceDocumentService {

    private final SourceDocumentRepository sourceDocumentRepository;
    private final SourceDocumentMapper sourceDocumentMapper;

    public SourceDocumentResponse saveFileMetadata(UUID userId, MultipartFile file) {
        log.info("Saving file metadata for user: {} - File: {}", userId, file.getOriginalFilename());

        // Stub logic for S3 Upload
        String fakeS3Url = "https://s3.amazonaws.com/ai-slides/" + UUID.randomUUID() + "/" + file.getOriginalFilename();

        SourceDocument doc = SourceDocument.builder()
                .userId(userId)
                .fileName(file.getOriginalFilename())
                .fileSize(file.getSize())
                .s3Url(fakeS3Url)
                .fileType(determineFileType(file.getOriginalFilename()))
                .build();

        doc = sourceDocumentRepository.save(doc);
        return sourceDocumentMapper.toDto(doc);
    }

    public List<SourceDocumentResponse> getDocumentsByUser(UUID userId) {
        List<SourceDocument> entities = sourceDocumentRepository.findByUserId(userId);
        return sourceDocumentMapper.toDto(entities);
    }

    public SourceDocumentResponse getDocument(UUID id, UUID userId) {
        SourceDocument entity = sourceDocumentRepository.findById(id)
                .orElseThrow(() -> new AppException(ErrorCode.DOCUMENT_NOT_FOUND));
        
        if (!entity.getUserId().equals(userId)) {
            throw new AppException(ErrorCode.ACCESS_DENIED);
        }
        
        return sourceDocumentMapper.toDto(entity);
    }

    @Transactional
    public void deleteDocuments(List<UUID> ids, UUID userId) {
        List<SourceDocument> docs = sourceDocumentRepository.findAllById(ids);

        for (SourceDocument doc : docs) {
            if (!doc.getUserId().equals(userId)) {
                throw new AppException(ErrorCode.ACCESS_DENIED);
            }
        }
        
        sourceDocumentRepository.deleteAllById(ids);
    }

    private Integer determineFileType(String fileName) {
        if (fileName == null) return Constants.DOCUMENT_TYPE.TEXT_PROMPT;
        if (fileName.toLowerCase().endsWith(".pdf")) return Constants.DOCUMENT_TYPE.PDF;
        if (fileName.toLowerCase().endsWith(".docx")) return Constants.DOCUMENT_TYPE.DOCX;
        return Constants.DOCUMENT_TYPE.TEXT_PROMPT;
    }
}
