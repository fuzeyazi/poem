package com.fuze.potryservice.service;

import com.fuze.dto.NoticeDto;
import com.fuze.result.PageResult;

import java.util.List;

public interface NoticeService {
    void add(NoticeDto noticeDto);

    void delete(List<Long> ids);

    PageResult GetPage(Integer pageNum, Integer pageSize);

    void update(NoticeDto noticeDto);

    List<NoticeDto> getNotice();
}
