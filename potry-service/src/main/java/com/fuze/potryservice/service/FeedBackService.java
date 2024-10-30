package com.fuze.potryservice.service;

import com.fuze.dto.FeedBackDto;
import com.fuze.dto.ReplyDto;
import com.fuze.entity.FeedBack;
import com.fuze.vo.FeedBackVo;
import com.github.pagehelper.PageInfo;

import java.util.List;

public interface FeedBackService {
    void addfeedback(FeedBackDto feedBackDto);

    List<FeedBack> getAllFeedBack();

    FeedBack getFeedBack(Integer id);

    void deletefeedback(Integer id);

    void addreply(ReplyDto replyDto);

    PageInfo<FeedBackVo> selectPage(Integer pageNum, Integer pageSize);

    String getReply(Integer id);
}
