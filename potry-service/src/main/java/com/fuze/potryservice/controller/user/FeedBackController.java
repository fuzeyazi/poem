package com.fuze.potryservice.controller.user;

import com.fuze.context.BaseContext;
import com.fuze.dto.FeedBackDto;
import com.fuze.entity.FeedBack;
import com.fuze.potryservice.service.FeedBackService;
import com.fuze.result.Result;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.redisson.api.RBucket;
import org.redisson.api.RedissonClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.List;

@RestController
@RequestMapping("/user/FeedBack")
@Api(tags = "用户留言反馈表相关接口")
@Slf4j
public class FeedBackController {

    @Autowired
    private FeedBackService feedBackService;

    @Autowired
    private RedissonClient redissonClient;

    @ApiOperation(value = "用户留言反馈")
    @PostMapping("/addfeedback")
    public Result<String> addfeedback(@RequestBody FeedBackDto feedBackDto) {
        Long currentId = BaseContext.getCurrentId();
        if (currentId != null && feedBackDto.getUserid() == null) {
            feedBackDto.setUserid(currentId.intValue());
        }

        RBucket<Object> feedback = redissonClient.getBucket("feedback");
        feedback.set(feedBackDto);

        feedBackService.addfeedback(feedBackDto);
        return Result.success("反馈成功");
    }

    @ApiOperation(value = "用户接受回复")
    @GetMapping("/getReply/{id}")
    public Result<String> getReply(@PathVariable Integer id) {
        return Result.success(feedBackService.getReply(id));
    }

    @ApiOperation(value = "用户查看自己的历史反馈列表")
    @GetMapping("/getAllFeedBack")
    public Result<List<FeedBack>> getAllFeedBack() {
        Long currentId = BaseContext.getCurrentId();
        if (currentId == null) {
            return Result.success(new ArrayList<>());
        }
        return Result.success(feedBackService.getFeedBackByUserId(currentId.intValue()));
    }
}
