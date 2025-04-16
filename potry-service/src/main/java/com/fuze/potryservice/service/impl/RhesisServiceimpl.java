package com.fuze.potryservice.service.impl;

import com.fuze.entity.Rhesis;
import com.fuze.potryservice.mapper.RhesisMapper;
import com.fuze.potryservice.service.RhesisService;
import com.fuze.result.PageResult;
import com.fuze.vo.PoemDataVo;
import com.fuze.vo.RhesisDataVo;
import com.github.pagehelper.Page;
import com.github.pagehelper.PageHelper;
import com.github.pagehelper.PageInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class RhesisServiceimpl implements RhesisService {
    @Autowired
    private RhesisMapper rhesisMapper;

    @Override
    public Integer getcount() {
        return rhesisMapper.getcount();
    }

    @Override
    public List<String> GetAllRhesisName() {
        return rhesisMapper.GetAllRhesisName();
    }

    @Override
    public Rhesis GetContentById(Integer id) {
        return rhesisMapper.GetContentById(id);
    }

    @Override
    public RhesisDataVo GetVeryGoodRhesis() {
        return rhesisMapper.GetVeryGoodPoem();
    }

    @Override
    public List<RhesisDataVo> GetRhesisByKey(String keyword) {
        return rhesisMapper.GetRhesisByKey(keyword);
    }

    @Override
    public List<RhesisDataVo> GetRhesisDateRondom() {
        return rhesisMapper.GetRhesisDateRondom();
    }




    @Override
    public PageResult GetRhesisPage(Integer pageNum, Integer pageSize) {
        PageHelper.startPage(pageNum, pageSize);
        Page<RhesisDataVo> page=rhesisMapper.GetRhesisDateRondom();
        long total = page.getTotal();
        List<RhesisDataVo> records = page.getResult();
        return new PageResult(total, records);

    }
}
