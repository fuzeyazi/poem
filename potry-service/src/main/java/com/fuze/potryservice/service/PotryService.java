package com.fuze.potryservice.service;

import com.fuze.entity.Poem;
import com.fuze.entity.Writer;
import com.fuze.entity.WriterEndVo;
import com.fuze.result.PageResult;
import com.fuze.vo.*;
import com.github.pagehelper.PageInfo;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Set;


public interface PotryService{
    Integer getcount();

    List<String> GetAllPoemName();

    Poem GetContentById(Integer id);

    List<String> GetAllDynasty();

    List<DynatryPoemResultVO> GetDynastyPoemResulVo();

    List<PoemDataVo> GetPoemDataVoByDynasty(String dynasty);

    List<PoemDataVo> GetPoemDateRondom();

//    PageInfo<PoemDataVo> GetPoemPage(Integer pageNum, Integer pageSize);

    List<PoemDataVo> GetPoemDataVoByWriter(String name);


    List<String> GetType();

    List<PoemDataVo> GetPoemDataByType(String type);

    List<Poem> GetContentBytitle(String title);

    PoemDataVo GetVeryGoodPoem();

    WriterEndVo GetPoemWriter(int id) throws InterruptedException;

    PageResult GetPoemPage(Integer pageNum, Integer pageSize);

    List<PoemVo> GetPoemBydynasty(String dynasty);

    PageResult GetPoemBydynastys(Integer pageNum, Integer pageSize, String dynasty);

    PageResult GetPoemByType(Integer pageNum, Integer pageSize, String type);

    PageResult GetwriterBydynasty(Integer pageNum, Integer pageSize, String dynsaty);

    PageResult GetwriterBydynasty1();

    List<Writer> GetRondWriter();

    PageResult GetwriterBydynasty11(Integer pageNum, Integer pageSize, String writer);

    PageResult GetwriterBydynasty111(Integer pageNum, Integer pageSize, String writer);

    List<Poem> GetContentBytitle1(Integer id);

    PageResult GetPoembyTitle(Integer pageNum, Integer pageSize, String title);

    PageResult GetwriterB(Integer pageNum, Integer pageSize, String title);

    String getcountbyid(int id);

    void update(Integer userid,Integer poemid);
}
