package com.fuze.potryservice.service;

import com.fuze.dto.AdminDto;
import com.fuze.dto.AdminLoginDto;
import com.fuze.dto.PotryDTO;
import com.fuze.dto.RhesisDto;
import com.fuze.entity.Admin;
import com.fuze.entity.Suggestion;
import com.fuze.result.PageResult;
import jakarta.mail.MessagingException;
import jakarta.servlet.http.HttpSession;

import java.io.UnsupportedEncodingException;
import java.util.List;

public interface AdminService {
    Admin login(AdminLoginDto adminLoginDto);

    void add(PotryDTO potryDTO);

    void delete(List<Long> ids);

    void register(AdminDto adminDto);

    String sendcode(String email, HttpSession session, int i) throws UnsupportedEncodingException, MessagingException;

    void update(PotryDTO potryDTO);
        void disable(Integer status,Integer id);

    List<PotryDTO> GetContent(PotryDTO potryDTO);

    void deleteByTitle(String title);

    void save(Suggestion suggestion);

    PageResult GetUser(Integer pageNum, Integer pageSize);

    PageResult GetPoem(Integer pageNum, Integer pageSize);

    PageResult GetBlog(Integer pageNum, Integer pageSize);

    void deleteBlogById(List<Integer> ids);

    PageResult GetAllRhesis(Integer pageNum, Integer pageSize);

    void deleteRhesisById(List<Integer> ids);

    void addRhesis(RhesisDto rhesisDto);

    void updateRhesis(RhesisDto rhesisDto);

    List<RhesisDto> GetRhesisByPoemName(String name);
}
