import React from 'react';
import styled from 'styled-components';

const FooterContainer = styled.footer`
  background-color: #f5f5f5;
  color: #666;
  padding: 1rem;
  text-align: center;
  border-top: 1px solid #ddd;
  font-size: 0.9rem;
`;

const FooterContent = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  
  @media (max-width: 768px) {
    flex-direction: column;
    gap: 0.5rem;
  }
`;

const Copyright = styled.div`
  flex: 1;
`;

const Links = styled.div`
  display: flex;
  gap: 1rem;
`;

const Link = styled.a`
  color: #4a90e2;
  text-decoration: none;
  
  &:hover {
    text-decoration: underline;
  }
`;

const Footer = () => {
  const currentYear = new Date().getFullYear();
  
  return (
    <FooterContainer>
      <FooterContent>
        <Copyright>
          &copy; {currentYear} AI Agent Interface. All rights reserved.
        </Copyright>
        
        <Links>
          <Link href="#">Documentation</Link>
          <Link href="#">Privacy Policy</Link>
          <Link href="#">Terms of Service</Link>
        </Links>
      </FooterContent>
    </FooterContainer>
  );
};

export default React.memo(Footer);
