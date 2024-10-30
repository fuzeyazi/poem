package com.fuze.potryservice.service;

import com.fuze.vo.PoemDataVo;
import com.fuze.vo.WriterVo;
import com.fuze.vo.WriterWithPoemsVo;
import com.github.pagehelper.PageInfo;

import java.util.List;

public interface WriterService {
    Integer getWriterCount();
    List<String> getAllWriterNames();
    List<String> getWritersByDynasty(String dynasty);
    List<PoemDataVo> getPoemsByWriter(String writer);
    List<PoemDataVo> getRandomPoems();
    WriterVo getImageAndSimpleIntroByName(String name);
    String getDetailIntroByName(String name);
    WriterWithPoemsVo getWriterAndPoemsById(Long id);
    List<String> getAllDynasties();
    PoemDataVo getFamousLinesByWriterId(Long id);
    PageInfo<WriterVo> getWritersByPage(int pageNum, int pageSize);
    List<WriterVo> getRandomWriters();
}

