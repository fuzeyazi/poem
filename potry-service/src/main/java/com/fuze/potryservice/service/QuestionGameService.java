package com.fuze.potryservice.service;

import com.fuze.vo.GameRankVo;
import com.github.pagehelper.PageInfo;

import java.util.List;

public interface QuestionGameService {
    void addQuestion(String s);

    String getQuestion();

    void deleteQuestion();

    void addsum(int sum, Integer userId,String name);

    String getusername(Integer userId);

    List<GameRankVo> getRank();

    PageInfo<GameRankVo> selectPageVO(Integer pageNum, Integer pageSize);

    void delete(Integer id);

    List<GameRankVo> getuserRank(Integer userid);
}
