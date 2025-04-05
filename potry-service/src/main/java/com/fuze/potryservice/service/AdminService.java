package com.fuze.potryservice.service;

import com.fuze.dto.AdminDto;
import com.fuze.dto.AdminLoginDto;
import com.fuze.dto.PotryDTO;
import com.fuze.entity.Admin;
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
}
