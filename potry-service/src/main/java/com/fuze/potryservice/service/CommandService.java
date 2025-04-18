package com.fuze.potryservice.service;

import com.fuze.dto.CommentAiDto;

import java.util.List;
import java.util.Map;

public interface CommandService {
    Map<String, String> process(String command);

    Object process1(CommentAiDto commentAiDto, List<String> list);
}
