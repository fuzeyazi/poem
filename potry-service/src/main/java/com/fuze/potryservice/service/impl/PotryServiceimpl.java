package com.fuze.potryservice.service.impl;

import com.fuze.entity.Poem;
import com.fuze.entity.Writer;
import com.fuze.entity.WriterEndVo;
import com.fuze.potryservice.mapper.PotryMapper;
import com.fuze.potryservice.service.PotryService;
import com.fuze.result.PageResult;
import com.fuze.vo.*;
import com.github.pagehelper.Page;
import com.github.pagehelper.PageHelper;
import com.github.pagehelper.PageInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;

@Service
public class PotryServiceimpl implements PotryService {
    @Autowired
    private PotryMapper potryMapper;
    @Override
    public Integer getcount() {
       return potryMapper.getcount();
    }

    @Override
    public List<String> GetAllPoemName() {
        return potryMapper.GetAllPoemName();
    }

    @Override
    public Poem GetContentById(Integer id) {
        Poem poem = potryMapper.GetContentById(id);
        if (poem != null) {
            String content = poem.getContent();
            String remarks = poem.getRemarks();
            String translation = poem.getTranslation();
            String shangxi = poem.getShangxi();

            if (content != null) {
                content = content.replace("\r\n", "<br>");
            }
            if (remarks != null) {
                remarks = remarks.replace("\r\n", "<br>");
            }
            if (translation != null) {
                translation = translation.replace("\r\n", "<br>");
            }
            if (shangxi != null) {
                shangxi = shangxi.replace("\r\n", "<br>");
            }

            poem.setShangxi(shangxi);
            poem.setContent(content);
            poem.setRemarks(remarks);
            poem.setTranslation(translation);
        }

        return poem;
    }
    @Override
    public List<String> GetAllDynasty() {
        return potryMapper.Getdynasty();
    }

    @Override
    public List<DynatryPoemResultVO> GetDynastyPoemResulVo() {
        return potryMapper.GetDynastyPoemResulVo();
    }

    @Override
    public List<PoemDataVo> GetPoemDataVoByDynasty(String dynasty) {
        return potryMapper.GetPoemDataVoByDynasty(dynasty);
    }

    @Override
    public List<PoemDataVo> GetPoemDateRondom() {
        return potryMapper.GetPoemDateRondom();

    }
    @Override
    public PageResult GetPoemPage(Integer pageNum, Integer pageSize) {
        PageHelper.startPage(pageNum, pageSize);
        Page<PoemDataVo> page = potryMapper.GetPoemvoByPage1();
        long total = page.getTotal();
        List<PoemDataVo> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public List<PoemVo> GetPoemBydynasty(String dynasty) {
        return potryMapper.GetPoemBydynasty(dynasty);
    }

    @Override
    public PageResult GetPoemBydynastys(Integer pageNum, Integer pageSize, String dynasty) {
        PageHelper.startPage(pageNum, pageSize);
        Page<PoemVo> page=potryMapper.GetPoemBydynasty(dynasty);
        long total = page.getTotal();
        List<PoemVo> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public PageResult GetPoemByType(Integer pageNum, Integer pageSize, String type) {
        PageHelper.startPage(pageNum, pageSize);
        Page<PoemDataVo> page=potryMapper.GetPoemByType(type);
        long total = page.getTotal();
        List<PoemDataVo> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public PageResult GetwriterBydynasty(Integer pageNum, Integer pageSize, String dynasty) {
        PageHelper.startPage(pageNum, pageSize);
        Page<Writer> page=potryMapper.GetwriterBydynasty(dynasty);
        long total = page.getTotal();
        List<Writer> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public PageResult GetwriterBydynasty1() {
        return potryMapper.GetwriterBydynasty1();
    }

    @Override
    public List<Writer> GetRondWriter() {
        return potryMapper.GetRondWriter();
    }

    @Override
    public PageResult GetwriterBydynasty11(Integer pageNum, Integer pageSize, String writer) {
        PageHelper.startPage(pageNum, pageSize);
        Page<PoemDataVo> page=potryMapper.GetwriterBywriter(writer);
        long total = page.getTotal();
        List<PoemDataVo> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public PageResult GetwriterBydynasty111(Integer pageNum, Integer pageSize, String writer) {
        PageHelper.startPage(pageNum,pageSize);
        Page<RhesisDataVo> page=potryMapper.GetwriterBywriter1(writer);
        long total = page.getTotal();
        List<RhesisDataVo> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public List<Poem> GetContentBytitle1(Integer id) {
        Poem poem=potryMapper.GetContentById(id);
        if(poem.getRemarks()==null|| poem.getRemarks().isEmpty()){
            poem.setRemarks("暂时没有收录");
        }
        if(poem.getTranslation()==null|| poem.getTranslation().isEmpty()){
            poem.setTranslation("暂时没有收录");
        }
        if(poem.getShangxi()==null|| poem.getShangxi().isEmpty()){
            poem.setShangxi("暂时没有收录");
        }
        return Arrays.asList(poem);
    }

    @Override
    public List<PoemDataVo> GetPoemDataVoByWriter(String name) {
        return potryMapper.GetPoemData(name);
    }

    @Override
    public List<String> GetType() {
        List<String> list1=potryMapper.GetType();
        list1.removeIf(String::isEmpty);
        return list1;
    }

    @Override
    public List<PoemDataVo> GetPoemDataByType(String type) {
        return potryMapper.GetPoemDataByType(type);
    }

    @Override
    public List<Poem>  GetContentBytitle(String title) {
        return potryMapper.GetContentByTitle(title);
    }

    @Override
    public PoemDataVo GetVeryGoodPoem() {
        return potryMapper.GetVeryGoodPoem();
    }

    @Override
    public WriterEndVo GetPoemWriter(int id) {

        return potryMapper.GetPoemWriter(id);
    }


}
