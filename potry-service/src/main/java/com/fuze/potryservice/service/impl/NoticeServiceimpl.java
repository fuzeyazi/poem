package com.fuze.potryservice.service.impl;

import cn.hutool.core.date.DateUnit;
import cn.hutool.core.date.DateUtil;
import com.fuze.dto.NoticeDto;
import com.fuze.entity.Notice;
import com.fuze.potryservice.mapper.NoticeMapper;
import com.fuze.potryservice.service.NoticeService;
import com.fuze.result.PageResult;
import com.fuze.vo.PoemDataVo;
import com.github.pagehelper.Page;
import com.github.pagehelper.PageHelper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

@Slf4j
@Service
public class NoticeServiceimpl implements NoticeService {
    @Autowired
    private NoticeMapper noticeMapper;
    @Override
    public void add(NoticeDto noticeDto) {
        Notice notice = new Notice();
        //log.info("添加公告:{}", noticeDto);
        BeanUtils.copyProperties(noticeDto, notice);
        //log.info("添加公告:{}", notice);
        notice.setCreatetime(DateUtil.now());
        noticeMapper.add(notice);
    }

    @Override
    public void delete(List<Long> ids) {
        for(Long id : ids)
        {
            noticeMapper.delete(id);
        }
    }

    @Override
    public PageResult GetPage(Integer pageNum, Integer pageSize) {
        PageHelper.startPage(pageNum, pageSize);
        Page<Notice> page = noticeMapper.GetNoticeByPage();
        long total = page.getTotal();
        List<Notice> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public void update(NoticeDto noticeDto) {
        Notice notice = new Notice();
        BeanUtils.copyProperties(noticeDto, notice);
        noticeMapper.update(notice);
    }

    @Override
    public List<NoticeDto> getNotice() {
        return noticeMapper.getNotice();
    }
}
