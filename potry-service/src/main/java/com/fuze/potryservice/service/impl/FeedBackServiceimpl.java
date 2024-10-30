package com.fuze.potryservice.service.impl;

import com.fuze.dto.FeedBackDto;
import com.fuze.dto.ReplyDto;
import com.fuze.entity.FeedBack;
import com.fuze.potryservice.mapper.FeedBackMapper;
import com.fuze.potryservice.service.FeedBackService;
import com.fuze.vo.FeedBackVo;
import com.fuze.vo.PoemDataVo;
import com.github.pagehelper.PageHelper;
import com.github.pagehelper.PageInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class FeedBackServiceimpl implements FeedBackService {
    @Autowired
    private FeedBackMapper feedBackMapper;
    @Override
    public void addfeedback(FeedBackDto feedBackDto) {

        feedBackMapper.addfeedback(feedBackDto);
    }

    @Override
    public List<FeedBack> getAllFeedBack() {
        return feedBackMapper.getAllFeedBack();
    }

    @Override
    public FeedBack getFeedBack(Integer id) {
        return feedBackMapper.getFeedBack(id);
    }

    @Override
    public void deletefeedback(Integer id) {
        feedBackMapper.deletefeedback(id);
    }

    @Override
    public void addreply(ReplyDto replyDto) {
        feedBackMapper.addreply(replyDto);
    }

    @Override
    public PageInfo<FeedBackVo> selectPage(Integer pageNum, Integer pageSize) {
        PageHelper.startPage(pageNum,pageSize);
        List<FeedBackVo> lis1 = feedBackMapper.Getpage();
        return new PageInfo<>(lis1);
    }

    @Override
    public String getReply(Integer id) {
        return feedBackMapper.getReply(id);
    }
}
