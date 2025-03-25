import React from 'react';
import styled from 'styled-components';

const HeaderContainer = styled.header`
  background-color: #2c3e50;
  color: white;
  padding: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
`;

const Logo = styled.div`
  font-size: 1.5rem;
  font-weight: bold;
  display: flex;
  align-items: center;
  
  svg {
    margin-right: 10px;
  }
`;

const Navigation = styled.nav`
  display: flex;
  gap: 1rem;
  
  @media (max-width: 768px) {
    display: none;
  }
`;

const NavLink = styled.a`
  color: white;
  text-decoration: none;
  padding: 0.5rem;
  border-radius: 4px;
  transition: background-color 0.2s;
  
  &:hover {
    background-color: rgba(255, 255, 255, 0.1);
  }
`;

const Header = () => {
  return (
    <HeaderContainer>
      <Logo>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M2 17L12 22L22 17" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M2 12L12 17L22 12" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        AI Agent Interface
      </Logo>
      
      <Navigation>
        <NavLink href="#">Dashboard</NavLink>
        <NavLink href="#">Tasks</NavLink>
        <NavLink href="#">Knowledge</NavLink>
        <NavLink href="#">Settings</NavLink>
      </Navigation>
    </HeaderContainer>
  );
};

export default React.memo(Header);
