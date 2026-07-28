package com.backend.documentservice.converter;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;

import java.util.Collections;
import java.util.List;

@Converter
public class StringListConverter implements AttributeConverter<List<String>, String> {
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();
    private static final TypeReference<List<String>> STRING_LIST = new TypeReference<>() {};

    @Override
    public String convertToDatabaseColumn(List<String> value) {
        if (value == null) return null;
        try {
            return OBJECT_MAPPER.writeValueAsString(value);
        } catch (Exception exception) {
            throw new IllegalArgumentException("Cannot serialize string list", exception);
        }
    }

    @Override
    public List<String> convertToEntityAttribute(String value) {
        if (value == null || value.isBlank()) return Collections.emptyList();
        try {
            return OBJECT_MAPPER.readValue(value, STRING_LIST);
        } catch (Exception exception) {
            return Collections.emptyList();
        }
    }
}
