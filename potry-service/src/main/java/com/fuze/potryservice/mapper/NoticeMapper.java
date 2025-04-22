package com.fuze.potryservice.mapper;

import com.fuze.dto.NoticeDto;
import com.fuze.entity.Notice;
import com.fuze.enumeration.OperationType;
import com.fuze.vo.PoemDataVo;
import com.github.pagehelper.Page;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface NoticeMapper {
    @Insert("insert into poem.notice(name,contents,createtime) values(#{name},#{contents},#{createtime})")
    void add(Notice notice);
@Delete("delete from poem.notice where id=#{id}")
    void delete(Long id);
@Select("select * from poem.notice")
    Page<Notice> GetNoticeByPage();

    void update(Notice notice);
@Select("select * from poem.notice")
    List<NoticeDto> getNotice();
}
