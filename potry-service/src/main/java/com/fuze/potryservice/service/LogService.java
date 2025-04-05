package com.fuze.potryservice.service;

import com.fuze.result.PageResult;

public interface LogService {
    PageResult GetLog(Integer pageNum, Integer pageSize);
    void addLog(String title, String time);
}
