package com.fuze.potryservice.service.impl;

import com.fuze.potryservice.mapper.WriterMapper;
import com.fuze.potryservice.service.WriterService;
import com.fuze.vo.PoemDataVo;
import com.fuze.vo.WriterVo;
import com.fuze.vo.WriterWithPoemsVo;
import com.github.pagehelper.PageHelper;
import com.github.pagehelper.PageInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class WriterServiceImpl implements WriterService {

    @Autowired
    private WriterMapper writerMapper;

    @Override
    public Integer getWriterCount() {
        return writerMapper.getWriterCount();
    }

    @Override
    public List<String> getAllWriterNames() {
        return writerMapper.getAllWriterNames();
    }

    @Override
    public List<String> getWritersByDynasty(String dynasty) {
        return writerMapper.selectWritersByDynasty(dynasty);
    }

    @Override
    public List<PoemDataVo> getPoemsByWriter(String writer) {
        return writerMapper.selectPoemsByWriter(writer);
    }

    @Override
    public List<PoemDataVo> getRandomPoems() {
        return writerMapper.getRandomPoems();
    }

    @Override
    public WriterVo getImageAndSimpleIntroByName(String name) {
        return writerMapper.selectImageAndSimpleIntroByName(name);
    }

    @Override
    public String getDetailIntroByName(String name) {
        return writerMapper.selectDetailIntroByName(name);
    }

    @Override
    public WriterWithPoemsVo getWriterAndPoemsById(Long id) {
        return writerMapper.selectWriterAndPoemsById(id);
    }

    @Override
    public List<String> getAllDynasties() {
        return writerMapper.selectAllDynasties();
    }

    @Override
    public PoemDataVo getFamousLinesByWriterId(Long id) {
        return writerMapper.selectFamousLinesByWriterId(id);
    }

    @Override
    public PageInfo<WriterVo> getWritersByPage(int pageNum, int pageSize) {
        PageHelper.startPage(pageNum, pageSize);
        List<WriterVo> writers = writerMapper.selectAllWriters();
        return new PageInfo<>(writers);
    }

    @Override
    public List<WriterVo> getRandomWriters() {
        return writerMapper.selectRandomWriters();
    }
}

