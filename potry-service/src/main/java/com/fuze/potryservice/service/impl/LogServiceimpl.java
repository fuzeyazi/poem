package com.fuze.potryservice.service.impl;

import com.fuze.entity.Log;
import com.fuze.potryservice.mapper.LogMapper;
import com.fuze.potryservice.service.LogService;
import com.fuze.result.PageResult;
import com.fuze.vo.PoemDataVo;
import com.github.pagehelper.Page;
import com.github.pagehelper.PageHelper;
import org.apache.ibatis.annotations.Select;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class LogServiceimpl implements LogService {
    @Autowired
    private LogMapper logMapper;
    @Override
    public PageResult GetLog(Integer pageNum, Integer pageSize) {
        PageHelper.startPage(pageNum, pageSize);
        Page<Log> page = logMapper.GetLog();
        long total = page.getTotal();
        List<Log> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public void addLog(String title, String time) {
        logMapper.addLog(title, time);
    }
}
