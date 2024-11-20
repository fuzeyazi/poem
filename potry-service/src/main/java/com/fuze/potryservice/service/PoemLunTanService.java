package com.fuze.potryservice.service;

import com.fuze.dto.FourCommentDtoPlus;
import com.fuze.dto.FourmCommentDto;
import com.fuze.dto.PoemBlogDto;
import com.fuze.result.PageResult;
import com.fuze.result.Result;
import com.fuze.vo.*;

import java.util.List;

public interface PoemLunTanService {
    void fabu(PoemBlogDto poemBlogDto,Integer id);

    PoemBlogVo selectxiangxi(Integer blogid);

    boolean dianzan(Integer blogid);

    List<UserDianZanVo> dianzanrank(Integer blogid);

    boolean isfrend(Integer followUserid);

    Result guanzhu(Integer followUserid, boolean isFollow);

    PageResult GetPoemPage(Integer pageNum, Integer pageSize,String type);

    BlogUserVo getByUsername(Integer followid);

    PageResult selecttiezi(Integer pageNum, Integer pageSize, Integer followid);


    Result selectguanzhu(Long lasttimemax, Long offset);

    Result fabucomment(FourmCommentDto fourmCommentDto, Integer id);

    List<FabaCommnetVo> selectConmmets(Integer blogid);

    boolean commentdianzan(Integer commentid);

    PageResult selectConmmets1(Integer blogid, Integer pageNum, Integer pageSize);

    List<PoemBlogVo> selectforum();

    List<BlogVO> selectforum1();

    List<PoemSerchVo> search(String content);
}
