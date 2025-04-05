package com.fuze.potryservice.service.impl;

import com.fuze.potryservice.mapper.QuestionGameMapper;
import com.fuze.potryservice.service.QuestionGameService;
import com.fuze.vo.GameRankVo;
import com.github.pagehelper.PageHelper;
import com.github.pagehelper.PageInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class QuestionGameServiceImpl implements QuestionGameService {
    @Autowired
    private QuestionGameMapper questionGameMapper;
    @Override
    public void addQuestion(String s) {
        questionGameMapper.addQuestion(s);
    }

    @Override
    public String getQuestion() {
        return questionGameMapper.getquestion();
    }

    @Override
    public void deleteQuestion() {
        questionGameMapper.deleteQuestion();
    }

    @Override
    public void addsum(int sum, Integer userId,String name) {
        questionGameMapper.addsum(sum, userId,name);
    }

    @Override
    public String getusername(Integer userId) {
        return questionGameMapper.getusename(userId);
    }

    @Override
    public List<GameRankVo> getRank() {
        return questionGameMapper.getRank();
    }

    @Override
    public PageInfo<GameRankVo> selectPageVO(Integer pageNum, Integer pageSize) {
        PageHelper.startPage(pageNum,pageSize);
        List<GameRankVo> list = questionGameMapper.getalluser();
        return new PageInfo<>(list);
    }

    @Override
    public void delete(Integer id) {
        questionGameMapper.delete(id);
    }

    @Override
    public List<GameRankVo> getuserRank(Integer userid) {
        return questionGameMapper.getuserRanl(userid);
    }
}
