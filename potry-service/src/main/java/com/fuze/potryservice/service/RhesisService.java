package com.fuze.potryservice.service;

import com.fuze.entity.Poem;
import com.fuze.entity.Rhesis;
import com.fuze.vo.PoemDataVo;
import com.fuze.vo.RhesisDataVo;
import com.github.pagehelper.PageInfo;
import org.springframework.stereotype.Service;

import java.util.List;

public interface RhesisService {
    Rhesis GetContentById(Integer id);

    Integer getcount();

    List<String> GetAllRhesisName();

    RhesisDataVo GetVeryGoodRhesis();

    List<RhesisDataVo> GetRhesisByKey(String keyword);

    List<RhesisDataVo> GetRhesisDateRondom();

    PageInfo<RhesisDataVo> GetRhesisPage(Integer pageNum, Integer pageSize);
}
